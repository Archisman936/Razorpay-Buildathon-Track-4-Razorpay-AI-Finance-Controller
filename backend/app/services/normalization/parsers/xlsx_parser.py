"""
XLSX Parser — Step 4 (Excel variant)

Parses XLSX/XLS files into list of record dicts.
Requires openpyxl (XLSX) or xlrd (XLS).
"""

import os
from typing import Iterator, Optional


class ParseError(Exception):
    pass


def validate_xlsx_file(filepath: str) -> dict:
    """
    Validate an Excel file before parsing.
    """
    if not os.path.exists(filepath):
        raise ParseError(f"File not found: {filepath}")

    if os.path.getsize(filepath) == 0:
        raise ParseError(f"File is empty: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()
    if ext not in (".xlsx", ".xls", ".xlsm"):
        raise ParseError(f"Unexpected extension '{ext}' for XLSX parser")

    return {"valid": True, "format": ext}


def parse_xlsx(filepath: str, sheet_name=0,
               header_row: int = 0,
               required_columns: list = None) -> Iterator[dict]:
    """
    Parse an Excel file, yielding one record dict per row.

    Requires openpyxl. Falls back to xlrd for .xls files.

    Args:
        filepath: Path to Excel file
        sheet_name: Sheet index (int) or name (str)
        header_row: Row index of the header (0-based)
        required_columns: List of required column names

    Yields:
        dict with row data, or parse_error dict
    """
    validate_xlsx_file(filepath)

    ext = os.path.splitext(filepath)[1].lower()

    try:
        import openpyxl
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)

        if isinstance(sheet_name, int):
            ws = wb.worksheets[sheet_name]
        else:
            ws = wb[sheet_name]

        rows = list(ws.iter_rows(values_only=True))

    except ImportError:
        raise ParseError(
            "openpyxl is required for XLSX parsing. "
            "Install with: pip install openpyxl"
        )
    except Exception as e:
        raise ParseError(f"Failed to open Excel file {filepath}: {e}")

    if not rows:
        return

    # Extract headers from header row
    headers = [str(h).strip() if h is not None else f"col_{i}"
               for i, h in enumerate(rows[header_row])]

    if required_columns:
        missing = [c for c in required_columns if c not in headers]
        if missing:
            raise ParseError(f"Excel missing required columns: {missing}")

    # Yield data rows
    for row_num, row in enumerate(rows[header_row + 1:], start=header_row + 2):
        # Skip completely empty rows
        if all(v is None for v in row):
            continue

        record = {}
        for i, (header, value) in enumerate(zip(headers, row)):
            if value is None:
                record[header] = None
            elif hasattr(value, "isoformat"):  # datetime/date
                record[header] = value.isoformat()
            else:
                record[header] = str(value).strip()

        yield record
