"""
Lineage Metadata — Step 16

Attaches source provenance to every canonical record.

Every normalized record must carry:
  source              — where it came from (BANK, RAZORPAY_API, etc.)
  source_record_id    — the original ID in the source system
  source_file_id      — which file it came from
  source_row_number   — row position in that file
  ingested_at         — when it was processed
  normalizer_version  — version of this normalization code

This allows tracing: PostgreSQL record → normalized record → original source.
"""

from datetime import datetime, timezone
from typing import Optional

NORMALIZER_VERSION = "v1.0.0"


def attach_lineage(
    canonical: dict,
    source: str,
    source_record_id: str,
    source_file_id: str,
    source_row_number: int,
    source_document_page: Optional[int] = None,
    ingested_at: Optional[datetime] = None,
) -> dict:
    """
    Attach lineage metadata to a canonical record dict (in-place and return).

    Args:
        canonical: The normalized record dict
        source: Source system (e.g. "BANK", "RAZORPAY_API", "SYNTHETIC")
        source_record_id: Original ID in source (e.g. "BNK_000001")
        source_file_id: File identifier (e.g. "FILE_019" or filename)
        source_row_number: Row/line number in source file
        source_document_page: For PDFs, the page number
        ingested_at: Timestamp of ingestion (defaults to now UTC)

    Returns:
        The same dict with _lineage key added
    """
    if ingested_at is None:
        ingested_at = datetime.now(tz=timezone.utc)

    canonical["_lineage"] = {
        "source": source.upper(),
        "source_record_id": source_record_id,
        "source_file_id": source_file_id,
        "source_row_number": source_row_number,
        "source_document_page": source_document_page,
        "ingested_at": ingested_at.isoformat(),
        "normalizer_version": NORMALIZER_VERSION,
    }

    return canonical


def extract_lineage(canonical: dict) -> dict:
    """Extract the lineage metadata from a canonical record."""
    return canonical.get("_lineage", {})


def lineage_to_flat(canonical: dict) -> dict:
    """
    Flatten lineage into top-level fields for PostgreSQL insertion.

    Example:
        _lineage.source → lineage_source
    """
    lineage = canonical.get("_lineage", {})
    return {
        "lineage_source":          lineage.get("source"),
        "lineage_source_record_id": lineage.get("source_record_id"),
        "lineage_source_file_id":  lineage.get("source_file_id"),
        "lineage_source_row":      lineage.get("source_row_number"),
        "lineage_ingested_at":     lineage.get("ingested_at"),
        "lineage_normalizer_ver":  lineage.get("normalizer_version"),
    }
