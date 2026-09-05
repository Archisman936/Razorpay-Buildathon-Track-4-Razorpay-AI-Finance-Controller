"""
Duplicate Detection — Step 14

Identifies duplicate records before insertion using:
1. Exact dedup key: (source, source_record_id) — primary method
2. Content hash: hash of key financial fields — secondary method

IMPORTANT: Duplicate source record ≠ legitimate repeated financial event.
           A payment processed twice vs a duplicate file upload are different.
           This module handles file/upload-level duplicates.
"""

import hashlib
import json
from typing import Optional


def make_content_hash(record: dict, fields: list) -> str:
    """
    Create a SHA-256 hash of specific financial fields for content dedup.

    Args:
        record: Canonical record dict
        fields: List of field names to include in hash

    Returns:
        Hex hash string
    """
    content = {f: str(record.get(f, "")).strip().lower() for f in fields}
    canonical_str = json.dumps(content, sort_keys=True)
    return hashlib.sha256(canonical_str.encode()).hexdigest()


# Key fields to hash per entity type for content deduplication
CONTENT_HASH_FIELDS = {
    "payment":    ["payment_id", "amount", "currency", "order_id"],
    "bank":       ["amount", "transaction_date", "reference", "description"],
    "settlement": ["settlement_id", "net_amount", "utr"],
    "invoice":    ["invoice_number", "total_amount", "invoice_date"],
    "book":       ["entry_id", "debit", "credit", "account_code", "entry_date"],
    "fee":        ["fee_id", "payment_id", "fee_amount"],
    "refund":     ["refund_id", "payment_id", "refund_amount"],
}


class DuplicateDetector:
    """
    In-memory duplicate detector for a single ingestion batch.

    For cross-batch deduplication, check the PostgreSQL
    normalization_source_map table instead.
    """

    def __init__(self):
        self._dedup_keys = set()       # (source, source_record_id) keys
        self._content_hashes = set()   # Content-based hashes

    def is_duplicate_by_key(self, source: str, source_record_id: str) -> bool:
        """Check if (source, source_record_id) was already seen."""
        key = f"{source.upper()}::{source_record_id}"
        if key in self._dedup_keys:
            return True
        self._dedup_keys.add(key)
        return False

    def is_duplicate_by_content(self, record: dict,
                                  entity_type: str) -> bool:
        """Check if a content-equivalent record was already seen."""
        fields = CONTENT_HASH_FIELDS.get(entity_type.lower(), [])
        if not fields:
            return False
        h = make_content_hash(record, fields)
        if h in self._content_hashes:
            return True
        self._content_hashes.add(h)
        return False

    def check(self, record: dict, source: str,
               source_record_id: str, entity_type: str) -> dict:
        """
        Full duplicate check.

        Returns:
            {"is_duplicate": bool, "method": "KEY"|"CONTENT"|None}
        """
        if self.is_duplicate_by_key(source, source_record_id):
            return {"is_duplicate": True, "method": "KEY"}

        if self.is_duplicate_by_content(record, entity_type):
            return {"is_duplicate": True, "method": "CONTENT"}

        return {"is_duplicate": False, "method": None}
