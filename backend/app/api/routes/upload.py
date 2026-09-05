"""File upload endpoint — ingest CSV, XLSX, or PDF into the normalization pipeline."""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/upload", tags=["upload"])

# Supported MIME types / extensions
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".pdf", ".jsonl", ".json"}
ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/pdf",
    "application/json",
    "application/x-ndjson",
    "text/plain",
}

# Data source types supported
SUPPORTED_SOURCE_TYPES = [
    "bank_record",
    "payment",
    "order",
    "settlement",
    "invoice",
    "refund",
    "fee",
    "gst",
    "book",
    "adjustment",
    "auto_detect",
]


@router.get("/source-types")
def get_source_types() -> dict:
    """Return supported upload source types."""
    return {"source_types": SUPPORTED_SOURCE_TYPES}


@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
    source_type: Optional[str] = Form(default="auto_detect"),
) -> dict:
    """
    Upload a CSV, XLSX, XLS, or PDF file for normalization and ingestion.

    The file is saved to a temp directory, parsed via the existing parser
    pipeline, then records are counted and returned. Full DB upsert
    requires running the normalization pipeline (scripts/normalize_all.py)
    but the upload validates the file and reports record counts.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    if source_type and source_type not in SUPPORTED_SOURCE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported source_type '{source_type}'. Supported: {SUPPORTED_SOURCE_TYPES}",
        )

    # Save the uploaded file to a temp directory
    upload_id = str(uuid.uuid4())[:8]
    tmp_dir = Path(tempfile.gettempdir()) / "rzp_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{upload_id}_{file.filename.replace(' ', '_')}"
    tmp_path = tmp_dir / safe_name

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        with open(tmp_path, "wb") as f:
            f.write(content)

        file_size_kb = round(len(content) / 1024, 1)
        logger.info("Uploaded file %s (%s KB) to %s", file.filename, file_size_kb, tmp_path)

        # Parse based on extension
        records = []
        parse_errors = []
        detected_schema = source_type

        if ext == ".csv":
            from backend.app.services.normalization.parsers.csv_parser import parse_csv
            for record in parse_csv(str(tmp_path)):
                if record.get("__parse_error__"):
                    parse_errors.append(record)
                else:
                    records.append(record)

        elif ext in (".xlsx", ".xls"):
            from backend.app.services.normalization.parsers.xlsx_parser import parse_xlsx
            for record in parse_xlsx(str(tmp_path)):
                if record.get("__parse_error__"):
                    parse_errors.append(record)
                else:
                    records.append(record)

        elif ext == ".pdf":
            from backend.app.services.normalization.parsers.pdf_parser import parse_pdf
            pages = parse_pdf(str(tmp_path))
            # Count extracted tables as records
            for page in pages:
                for table in page.get("tables", []):
                    records.extend(table)
            if not records:
                # If no tables, count pages as "records"
                records = [{"page": p["page"], "text_length": len(p["text"])} for p in pages]

        elif ext in (".jsonl", ".json"):
            from backend.app.services.normalization.parsers.json_parser import parse_jsonl
            for record in parse_jsonl(str(tmp_path)):
                if record.get("__parse_error__"):
                    parse_errors.append(record)
                else:
                    records.append(record)

        # Auto-detect schema from first record
        if source_type in (None, "auto_detect") and records:
            from backend.app.services.normalization.mappings.schema_detector import (
                detect_schema, detect_schema_from_filename
            )
            detected_schema = detect_schema(records[0])
            if detected_schema == "UNKNOWN":
                detected_schema = detect_schema_from_filename(file.filename) or "UNKNOWN"

        total_rows = len(records) + len(parse_errors)

        # Ingest parsed records into PostgreSQL
        inserted_count = 0
        inserted_ids = []
        if records:
            from backend.app.services.normalization.ingestor import ingest_records
            inserted_count, detected_schema, inserted_ids = ingest_records(
                records, source_type=source_type or detected_schema, filename=file.filename
            )

        return {
            "upload_id": upload_id,
            "filename": file.filename,
            "file_size_kb": file_size_kb,
            "extension": ext,
            "source_type": source_type or "auto_detect",
            "detected_schema": detected_schema,
            "total_rows": total_rows,
            "valid_records": len(records),
            "inserted_records": inserted_count,
            "inserted_ids": inserted_ids[:10],
            "parse_errors": len(parse_errors),
            "status": "processed" if len(records) > 0 else "empty",
            "message": (
                f"Successfully parsed and ingested {inserted_count} records into PostgreSQL from '{file.filename}'. "
                f"Records are live and ready for reconciliation."
                if inserted_count > 0
                else f"No records could be parsed from '{file.filename}'."
            ),
            "sample_fields": list(records[0].keys())[:10] if records else [],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Upload processing failed for %s: %s", file.filename, e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process '{file.filename}': {str(e)}",
        ) from e
    finally:
        # Clean up temp file
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
