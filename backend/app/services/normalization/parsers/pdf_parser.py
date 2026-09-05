"""
PDF Parser — Step 4 (PDF variant)

Extracts text/tables from PDF files.

Approach:
1. Try pdfplumber for text + table extraction (preferred)
2. OCR fallback via pytesseract + pdf2image if pdfplumber yields no text

Use case: Bank statements, invoice PDFs, GST certificates.
"""

import os
import re
from typing import Optional


class ParseError(Exception):
    pass


def validate_pdf_file(filepath: str) -> dict:
    """
    Validate a PDF file before parsing.
    """
    if not os.path.exists(filepath):
        raise ParseError(f"File not found: {filepath}")

    if os.path.getsize(filepath) == 0:
        raise ParseError(f"File is empty: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()
    if ext != ".pdf":
        raise ParseError(f"Expected .pdf, got '{ext}'")

    # Minimal PDF magic number check
    with open(filepath, "rb") as f:
        header = f.read(5)
    if header != b"%PDF-":
        raise ParseError(f"File does not appear to be a valid PDF: {filepath}")

    return {"valid": True, "format": "pdf"}


def extract_text_from_pdf(filepath: str) -> list:
    """
    Extract text from all pages of a PDF.

    Returns:
        List of dicts: [{"page": 1, "text": "...", "tables": [...]}]

    """
    validate_pdf_file(filepath)
    pages = []
    # 1. Try pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(filepath) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                tables = page.extract_tables() or []

                structured_tables = []
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    headers = [str(h).strip() if h else f"col_{i}"
                               for i, h in enumerate(table[0])]
                    rows = []
                    for row in table[1:]:
                        if all(cell is None or str(cell).strip() == "" for cell in row):
                            continue
                        rows.append({
                            headers[i]: str(cell).strip() if cell is not None else None
                            for i, cell in enumerate(row)
                        })
                    if rows:
                        structured_tables.append(rows)

                pages.append({
                    "page": page_num,
                    "text": text.strip(),
                    "tables": structured_tables,
                })
        if pages:
            return pages
    except ImportError:
        pass
    except Exception:
        pass

    # 2. Fallback to pypdf
    try:
        import pypdf
        reader = pypdf.PdfReader(filepath)
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append({
                "page": page_num,
                "text": text.strip(),
                "tables": [],
            })
        if pages:
            return pages
    except ImportError:
        pass
    except Exception:
        pass

    if not pages:
        raise ParseError(
            "pdfplumber or pypdf is required for PDF parsing. "
            "Install with: pip install pdfplumber"
        )
    return pages


def extract_with_ocr_fallback(filepath: str) -> list:
    """
    Extract text using OCR when pdfplumber yields no text (scanned PDFs).

    Requires: pdf2image, pytesseract, Tesseract-OCR installed.
    """
    validate_pdf_file(filepath)

    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError:
        raise ParseError(
            "pdf2image and pytesseract are required for OCR fallback. "
            "Install with: pip install pdf2image pytesseract"
        )

    images = convert_from_path(filepath, dpi=300)
    pages = []
    for page_num, img in enumerate(images, start=1):
        text = pytesseract.image_to_string(img, lang="eng")
        pages.append({
            "page": page_num,
            "text": text.strip(),
            "tables": [],  # OCR doesn't extract structured tables
            "ocr": True,
        })

    return pages


def parse_pdf(filepath: str, use_ocr_fallback: bool = True) -> list:
    """
    Main PDF parser entry point.

    Tries pdfplumber first, falls back to OCR if no text extracted.

    Returns:
        List of page dicts with text and structured tables
    """
    pages = extract_text_from_pdf(filepath)

    # Check if any text was extracted
    total_text = sum(len(p["text"]) for p in pages)

    if total_text < 50 and use_ocr_fallback:
        try:
            return extract_with_ocr_fallback(filepath)
        except ParseError:
            pass  # Return pdfplumber results even if empty

    return pages
