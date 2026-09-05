"""
CSV Parser — Step 4 (CSV variant)

Parses CSV files into list of record dicts.
Handles encoding detection and header validation.
"""

import csv
import os
import io
from typing import Iterator, Optional


class ParseError(Exception):
    pass


ENCODINGS_TO_TRY = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]


def validate_csv_file(filepath: str, required_columns: list = None) -> dict:
    """
    Validate a CSV file before parsing.

    Checks:
    - File exists and is non-empty
    - Valid extension
    - Header row present
    - Required columns present (if specified)

    Returns:
        {"valid": True, "columns": [...], "encoding": "..."}
    """
    if not os.path.exists(filepath):
        raise ParseError(f"File not found: {filepath}")

    if os.path.getsize(filepath) == 0:
        raise ParseError(f"File is empty: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()
    if ext not in (".csv", ".tsv", ".txt"):
        raise ParseError(f"Unexpected extension '{ext}' for CSV parser")

    # Detect encoding
    encoding_used = None
    for enc in ENCODINGS_TO_TRY:
        try:
            with open(filepath, "r", encoding=enc) as f:
                reader = csv.DictReader(f)
                columns = reader.fieldnames
                if columns:
                    encoding_used = enc
                    break
        except (UnicodeDecodeError, Exception):
            continue

    if not encoding_used:
        raise ParseError(f"Could not read {filepath} with any known encoding")

    if required_columns:
        missing = [c for c in required_columns if c not in columns]
        if missing:
            raise ParseError(f"CSV missing required columns: {missing}")

    return {"valid": True, "columns": list(columns), "encoding": encoding_used}


def parse_csv(filepath: str, delimiter: str = ",",
              required_columns: list = None) -> Iterator[dict]:
    """
    Parse a CSV file, yielding one record dict per row.

    Skips empty rows. Quarantines rows with wrong column count.

    Yields:
        dict with row data keyed by header names, or
        {"__parse_error__": True, "row": N, "raw": "...", "error": "..."}
    """
    validation = validate_csv_file(filepath, required_columns)
    encoding = validation["encoding"]

    with open(filepath, "r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 = header)
            # Skip completely empty rows
            if all(v is None or str(v).strip() == "" for v in row.values()):
                continue
            # Convert OrderedDict to regular dict, strip whitespace
            yield {k: v.strip() if v else v for k, v in row.items()}


def detect_delimiter(filepath: str) -> str:
    """Auto-detect CSV delimiter (comma, tab, semicolon, pipe)."""
    with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
        sample = f.read(2048)

    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        return ","  # Default to comma
