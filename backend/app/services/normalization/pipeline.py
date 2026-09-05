"""
Normalization Pipeline — Main Orchestrator

Steps 1-21: Complete normalization flow:
  RAW SOURCE → Validate → Detect Schema → Parse → Map to Canonical
  → Normalize → Validate → Dedup → Lineage → Upsert → Post-Load Verify

Entry point:
    from backend.app.services.normalization.pipeline import NormalizationPipeline

    pipeline = NormalizationPipeline(db_config=...)
    result = pipeline.run_file("data/raw/noisy/bank_records.jsonl",
                                source="BANK", entity_type="bank")
"""

import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, project_root)

from backend.app.services.normalization.parsers.json_parser import (
    validate_json_file, parse_jsonl
)
from backend.app.services.normalization.mappings.schema_detector import (
    detect_schema, detect_schema_from_filename
)
from backend.app.services.normalization.transforms.text import (
    normalize_text, normalize_bank_narration, normalize_gstin
)
from backend.app.services.normalization.transforms.identifiers import (
    normalize_entity_id, normalize_utr, normalize_invoice_number,
    normalize_bank_reference, make_dedup_key
)
from backend.app.services.normalization.transforms.amounts import (
    normalize_amount_safe, format_amount
)
from backend.app.services.normalization.transforms.dates import (
    normalize_datetime_safe, to_iso_string, to_date_string
)
from backend.app.services.normalization.transforms.currency import (
    normalize_currency_safe
)
from backend.app.services.normalization.transforms.status import (
    normalize_status_safe
)
from backend.app.services.normalization.transforms.entities import (
    normalize_payment_method, normalize_entry_type, normalize_adjustment_type,
    normalize_supply_type
)
from backend.app.services.normalization.validation.financial import validate_record
from backend.app.services.normalization.validation.duplicates import DuplicateDetector
from backend.app.services.normalization.lineage import attach_lineage


# ── Entity type → status category mapping ────────────────────────────────────
ENTITY_STATUS_CATEGORY = {
    "payment":    "payment",
    "order":      "order",
    "settlement": "settlement",
    "refund":     "refund",
    "invoice":    "invoice",
    "bank":       "bank",
    "gst":        "gst",
}

# ── Amount fields per entity ──────────────────────────────────────────────────
AMOUNT_FIELDS = {
    "payment":    ["amount"],
    "order":      ["subtotal", "discount", "taxable_amount", "cgst", "sgst", "igst",
                   "total_tax", "total_amount"],
    "invoice":    ["subtotal", "discount", "taxable_amount", "cgst", "sgst", "igst",
                   "total_tax", "total_amount"],
    "settlement": ["gross_amount", "total_fees", "total_fee_tax",
                   "total_refunds", "total_adjustments", "net_amount"],
    "bank":       ["amount", "balance_after"],
    "book":       ["debit", "credit"],
    "fee":        ["fee_amount", "tax_amount", "total_fee"],
    "refund":     ["refund_amount"],
    "gst":        ["taxable_amount", "cgst", "sgst", "igst", "total_tax", "total_amount"],
    "adjustment": ["amount"],
}

# ── Date fields per entity ────────────────────────────────────────────────────
DATE_FIELDS = {
    "payment":    ["payment_date", "captured_at"],
    "order":      ["order_date"],
    "invoice":    ["invoice_date"],
    "settlement": ["settlement_date"],
    "bank":       ["transaction_date", "value_date"],
    "book":       ["entry_date"],
    "refund":     ["refund_date"],
    "adjustment": ["adjustment_date"],
}

# ── ID fields per entity ──────────────────────────────────────────────────────
ID_FIELDS = {
    "payment":    [("payment_id", "canonical_payment_id")],
    "order":      [("order_id", "canonical_order_id")],
    "invoice":    [("invoice_number", "normalized_invoice_number")],
    "settlement": [("settlement_id", "canonical_settlement_id")],
    "bank":       [("reference", "canonical_reference")],
    "book":       [("reference_id", "canonical_reference_id")],
}


class NormalizationPipeline:
    """
    End-to-end normalization pipeline for a single entity type.

    Usage:
        pipeline = NormalizationPipeline()
        result = pipeline.run_file(
            filepath="data/raw/noisy/bank_records.jsonl",
            source="SYNTHETIC_BANK",
            entity_type="bank",
            source_file_id="FILE_001"
        )
    """

    def __init__(self, db_writer=None):
        """
        Args:
            db_writer: Optional callable(canonical_record, entity_type) for DB upsert.
                       If None, pipeline runs in dry-run mode.
        """
        self.db_writer = db_writer
        self.dedup_detector = DuplicateDetector()
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    def normalize_record(self, raw: dict, entity_type: str,
                          source: str, source_file_id: str,
                          row_number: int) -> dict:
        """
        Normalize a single raw record through all transform steps.

        Returns canonical record dict (may contain _errors, _lineage keys).
        """
        canonical = dict(raw)  # Start with a copy
        errors = []

        # ── Step 6: Text normalization ───────────────────────
        if "description" in canonical:
            canonical["_raw_description"] = canonical["description"]
            canonical["description_normalized"] = normalize_bank_narration(
                canonical["description"]
            )
        if "merchant_name" in canonical:
            canonical["merchant_name"] = normalize_text(canonical["merchant_name"])
        if "seller_gstin" in canonical:
            canonical["seller_gstin"] = normalize_gstin(canonical["seller_gstin"])
        if "buyer_gstin" in canonical:
            canonical["buyer_gstin"] = normalize_gstin(canonical["buyer_gstin"])

        # ── Step 7: ID/reference normalization ───────────────
        for source_field, canonical_field in ID_FIELDS.get(entity_type, []):
            if source_field in canonical and canonical[source_field]:
                canonical[canonical_field] = normalize_entity_id(canonical[source_field])

        if "utr" in canonical:
            canonical["utr"] = normalize_utr(canonical["utr"])
        if "invoice_number" in canonical and "normalized_invoice_number" not in canonical:
            canonical["normalized_invoice_number"] = normalize_invoice_number(
                canonical["invoice_number"]
            )

        # ── Step 8: Amount normalization ──────────────────────
        for field in AMOUNT_FIELDS.get(entity_type, []):
            if field in canonical:
                amount, err = normalize_amount_safe(canonical[field], field)
                if err:
                    errors.append(f"AMOUNT_PARSE_ERROR: {field}: {err}")
                    canonical[field] = None
                else:
                    canonical[field] = format_amount(amount)

        # ── Step 9: Date/time normalization ───────────────────
        for field in DATE_FIELDS.get(entity_type, []):
            if field in canonical and canonical[field]:
                dt, err = normalize_datetime_safe(canonical[field], field)
                if err:
                    errors.append(f"DATE_PARSE_ERROR: {field}: {err}")
                    canonical[field] = None
                else:
                    # Use date-only string for date fields
                    if "date" in field and "time" not in field and "at" not in field:
                        canonical[field] = to_date_string(dt)
                    else:
                        canonical[field] = to_iso_string(dt)

        # ── Step 10: Currency normalization ───────────────────
        if "currency" in canonical:
            currency, err = normalize_currency_safe(canonical["currency"])
            if err:
                errors.append(f"CURRENCY_ERROR: {err}")
            canonical["currency"] = currency

        # ── Step 11: Status normalization ─────────────────────
        status_category = ENTITY_STATUS_CATEGORY.get(entity_type)
        if status_category and "status" in canonical and canonical["status"]:
            normalized_status, err = normalize_status_safe(
                canonical["status"], status_category
            )
            canonical["status"] = normalized_status

        # ── Step 12: Entity-specific normalization ────────────
        if "payment_method" in canonical:
            canonical["payment_method"] = normalize_payment_method(
                canonical["payment_method"]
            )
        if "entry_type" in canonical:
            canonical["entry_type"] = normalize_entry_type(canonical["entry_type"])
        if "adjustment_type" in canonical:
            canonical["adjustment_type"] = normalize_adjustment_type(
                canonical["adjustment_type"]
            )
        if "supply_type" in canonical:
            canonical["supply_type"] = normalize_supply_type(canonical["supply_type"])
        if "transaction_type" in canonical:
            canonical["transaction_type"] = canonical["transaction_type"].upper() \
                if canonical["transaction_type"] else None

        # ── Step 13: Missing/null handling ────────────────────
        # Required fields that must be present — mark missing ones as errors
        required_fields_map = {
            "payment":    ["payment_id", "order_id", "amount"],
            "order":      ["order_id", "merchant_id", "total_amount"],
            "invoice":    ["invoice_id", "order_id", "total_amount"],
            "settlement": ["settlement_id", "merchant_id", "net_amount"],
            "bank":       ["bank_record_id", "merchant_id", "amount"],
            "book":       ["entry_id", "merchant_id"],
            "fee":        ["fee_id", "payment_id", "fee_amount"],
            "refund":     ["refund_id", "payment_id", "refund_amount"],
            "gst":        ["gst_record_id", "invoice_id"],
            "adjustment": ["adjustment_id", "settlement_id"],
        }
        for field in required_fields_map.get(entity_type, []):
            if not canonical.get(field):
                errors.append(f"MISSING_REQUIRED: {field}")

        # ── Step 16: Lineage metadata ─────────────────────────
        source_record_id = (
            canonical.get(f"{entity_type}_id") or
            canonical.get("entry_id") or
            canonical.get("bank_record_id") or
            canonical.get("gst_record_id") or
            canonical.get("adjustment_id") or ""
        )
        attach_lineage(
            canonical, source, source_record_id,
            source_file_id, row_number
        )

        # Attach errors
        if errors:
            canonical["_errors"] = errors

        return canonical

    def run_file(self, filepath: str, source: str, entity_type: str,
                  source_file_id: str = None) -> dict:
        """
        Run normalization pipeline on a JSONL file.

        Returns:
            Summary dict with counts: total, normalized, quarantined, duplicates
        """
        if source_file_id is None:
            source_file_id = os.path.basename(filepath)

        print(f"\n  Normalizing {source_file_id} ({entity_type})...")

        counts = {
            "total": 0,
            "normalized": 0,
            "quarantined": 0,
            "duplicates": 0,
            "validation_errors": 0,
        }

        canonical_records = []
        quarantine_records = []

        # Parse line by line
        for row_num, raw in enumerate(parse_jsonl(filepath), start=1):
            counts["total"] += 1

            # Handle parse errors (quarantine)
            if raw.get("__parse_error__"):
                quarantine_records.append({
                    "source": source,
                    "source_record_id": f"ROW_{row_num}",
                    "source_file_id": source_file_id,
                    "source_row_number": row_num,
                    "entity_type": entity_type,
                    "raw_record": raw,
                    "error_type": "PARSE_ERROR",
                    "error_message": raw.get("error", "Unknown parse error"),
                    "failed_field": None,
                })
                counts["quarantined"] += 1
                continue

            # Step 14: Duplicate detection
            source_record_id = (
                raw.get(f"{entity_type}_id") or
                raw.get("entry_id") or
                raw.get("bank_record_id") or
                raw.get("gst_record_id") or
                raw.get("adjustment_id") or
                f"ROW_{row_num}"
            )
            dup_check = self.dedup_detector.check(raw, source, source_record_id, entity_type)
            if dup_check["is_duplicate"]:
                counts["duplicates"] += 1
                continue

            # Steps 6-16: Normalize
            canonical = self.normalize_record(
                raw, entity_type, source, source_file_id, row_num
            )

            # Step 15: Financial validation
            validation_errors = validate_record(canonical, entity_type)
            if validation_errors:
                all_errors = canonical.get("_errors", []) + validation_errors
                canonical["_errors"] = all_errors

            # Step 18: Quarantine if has blocking errors
            blocking = [e for e in canonical.get("_errors", [])
                        if "MISSING_REQUIRED" in e or "ARITHMETIC_FAIL" in e
                        or "AMOUNT_PARSE_ERROR" in e]

            if blocking:
                quarantine_records.append({
                    "source": source,
                    "source_record_id": source_record_id,
                    "source_file_id": source_file_id,
                    "source_row_number": row_num,
                    "entity_type": entity_type,
                    "raw_record": raw,
                    "error_type": "VALIDATION_ERROR",
                    "error_message": "; ".join(blocking),
                    "failed_field": blocking[0].split(":")[1].strip()
                        if ":" in blocking[0] else None,
                })
                counts["quarantined"] += 1
                counts["validation_errors"] += 1
                continue

            canonical_records.append(canonical)
            counts["normalized"] += 1

            # Step 19: Upsert to DB (if writer provided)
            if self.db_writer:
                try:
                    self.db_writer(canonical, entity_type)
                except Exception as e:
                    quarantine_records.append({
                        "source": source,
                        "source_record_id": source_record_id,
                        "source_file_id": source_file_id,
                        "source_row_number": row_num,
                        "entity_type": entity_type,
                        "raw_record": raw,
                        "error_type": "DB_ERROR",
                        "error_message": str(e),
                        "failed_field": None,
                    })
                    counts["quarantined"] += 1
                    counts["normalized"] -= 1

        counts["quarantine_records"] = quarantine_records
        counts["canonical_records"] = canonical_records

        print(f"    total={counts['total']} | normalized={counts['normalized']} | "
              f"quarantined={counts['quarantined']} | duplicates={counts['duplicates']}")

        return counts


def run_full_normalization(noisy_dir: str, output_dir: str) -> dict:
    """
    Run normalization on all noisy JSONL files.

    Outputs normalized JSONL + quarantine JSONL to output_dir.

    Args:
        noisy_dir: Path to data/raw/noisy/
        output_dir: Path to data/normalized/

    Returns:
        Summary of all entities
    """
    os.makedirs(output_dir, exist_ok=True)

    pipeline = NormalizationPipeline()

    # Entity type → (filename, source_name)
    entity_files = [
        ("merchants",   "merchants.jsonl",         "SYNTHETIC_MERCHANT",  "merchant"),
        ("customers",   "customers.jsonl",          "SYNTHETIC_CUSTOMER",  "customer"),
        ("orders",      "orders.jsonl",             "SYNTHETIC_ORDER",     "order"),
        ("invoices",    "invoices.jsonl",           "SYNTHETIC_INVOICE",   "invoice"),
        ("gst_records", "gst_records.jsonl",        "SYNTHETIC_GST",       "gst"),
        ("payments",    "payments.jsonl",           "SYNTHETIC_PAYMENT",   "payment"),
        ("fees",        "fees.jsonl",               "SYNTHETIC_FEE",       "fee"),
        ("refunds",     "refunds.jsonl",            "SYNTHETIC_REFUND",    "refund"),
        ("settlements", "settlements.jsonl",        "SYNTHETIC_SETTLEMENT","settlement"),
        ("bank_records","bank_records.jsonl",       "SYNTHETIC_BANK",      "bank"),
        ("books",       "books.jsonl",              "SYNTHETIC_BOOK",      "book"),
        ("adjustments", "adjustments.jsonl",        "SYNTHETIC_ADJUSTMENT","adjustment"),
    ]

    overall = {}

    for entity_name, filename, source, entity_type in entity_files:
        filepath = os.path.join(noisy_dir, filename)
        if not os.path.exists(filepath):
            print(f"  Skipping {filename} (not found)")
            continue

        result = pipeline.run_file(
            filepath=filepath,
            source=source,
            entity_type=entity_type,
            source_file_id=filename,
        )

        # Write normalized JSONL
        normalized_path = os.path.join(output_dir, filename)
        with open(normalized_path, "w", encoding="utf-8") as f:
            for record in result["canonical_records"]:
                # Remove internal metadata keys before writing
                clean = {k: v for k, v in record.items()
                         if not k.startswith("__")}
                f.write(json.dumps(clean, ensure_ascii=False) + "\n")

        # Write quarantine JSONL
        if result["quarantine_records"]:
            q_path = os.path.join(output_dir, f"quarantine_{filename}")
            with open(q_path, "w", encoding="utf-8") as f:
                for record in result["quarantine_records"]:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")

        overall[entity_name] = {
            "total": result["total"],
            "normalized": result["normalized"],
            "quarantined": result["quarantined"],
            "duplicates": result["duplicates"],
        }

    return overall


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    noisy_dir = os.path.join(base_dir, "data", "raw", "noisy")
    output_dir = os.path.join(base_dir, "data", "normalized")

    print("=" * 60)
    print("  NORMALIZATION PIPELINE")
    print("=" * 60)

    summary = run_full_normalization(noisy_dir, output_dir)

    print("\n" + "=" * 60)
    print("  NORMALIZATION COMPLETE")
    print("=" * 60)
    print(f"\n  {'Entity':<20} {'Total':>8} {'Norm':>8} {'Quar':>8} {'Dup':>8}")
    print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    for entity, counts in summary.items():
        print(f"  {entity:<20} {counts['total']:>8} {counts['normalized']:>8} "
              f"{counts['quarantined']:>8} {counts['duplicates']:>8}")
    print(f"\n  Output: {output_dir}")
