"""
Canonical Normalization Pipeline — Phase 2 & 3
===============================================
Reads raw data from data/raw/synthetic/ and data/raw/noisy/,
canonicalizes ALL entity IDs and FK references,
preserves original noisy IDs in lineage,
deduplicates by canonical PK (synthetic is authoritative on conflict),
quarantines records with unresolvable IDs,
writes clean normalized JSONL to data/normalized/.

Key design decisions:
  1. Canonical format: PREFIX_XXXXXX (e.g., ORD_000123)
  2. Original noisy ID stored in _lineage.source_record_id
  3. Synthetic source is authoritative over noisy source on PK conflict
  4. Amount / date / description corruption is PRESERVED (ML test cases)
  5. Records with unresolvable IDs are quarantined (not loaded into DB)
  6. Normalization is deterministic (seed-based, same input → same output)

Usage:
    python scripts/normalize_all.py [--dry-run]
"""

import copy
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Optional

# Allow imports from project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.app.services.normalization.transforms.id_canonicalizer import (
    canonicalize_id,
    try_canonicalize_id,
    CanonicalizeError,
)

# ── Paths ─────────────────────────────────────────────────────────────────
RAW_SYNTH   = os.path.join(PROJECT_ROOT, "data", "raw", "synthetic")
RAW_NOISY   = os.path.join(PROJECT_ROOT, "data", "raw", "noisy")
NORMALIZED  = os.path.join(PROJECT_ROOT, "data", "normalized")
GT_DIR      = os.path.join(PROJECT_ROOT, "data", "ground_truth")
QUARANTINE_DIR = os.path.join(PROJECT_ROOT, "data", "normalized", "quarantine")

NORMALIZER_VERSION = "v2.0.0"
INGESTED_AT = datetime.now(timezone.utc).isoformat()


# ── Helpers ───────────────────────────────────────────────────────────────

def load_jsonl(path: str) -> list:
    """Load JSONL; skip blank/malformed lines."""
    records = []
    if not os.path.exists(path):
        return records
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append((i, json.loads(line)))
            except json.JSONDecodeError as e:
                print(f"  [WARN] {path}:{i} malformed JSON: {e}")
    return records  # list of (row_number, record_dict)


def write_jsonl(records: list, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


def make_lineage(source: str, source_record_id: str, source_file_id: str,
                 row_number: int) -> dict:
    return {
        "source": source,
        "source_record_id": source_record_id,
        "source_file_id": os.path.basename(source_file_id),
        "source_row_number": row_number,
        "source_document_page": None,
        "ingested_at": INGESTED_AT,
        "normalizer_version": NORMALIZER_VERSION,
    }


def quarantine_record(record: dict, entity_type: str, source: str,
                      row_number: int, source_file: str,
                      reason: str, field: str = None) -> dict:
    """Package a record for the quarantine file."""
    return {
        "quarantined_at": INGESTED_AT,
        "entity_type": entity_type,
        "source": source,
        "source_file": os.path.basename(source_file),
        "source_row": row_number,
        "reason": reason,
        "failed_field": field,
        "raw_record": record,
    }


# ── Entity-specific normalization functions ────────────────────────────────

def normalize_entity(
    rows_synth: list,       # list of (row_num, raw_dict)
    rows_noisy: list,       # list of (row_num, raw_dict)
    entity_type: str,
    pk_field: str,
    fk_fields: list,        # list of FK field names to canonicalize
    synth_source_name: str,
    noisy_source_name: str,
    source_file: str,
) -> tuple:
    """
    Generic normalization for any entity.
    Returns (canonical_records_dict, quarantine_list)
    canonical_records_dict: {canonical_pk: record}  (synthetic wins on conflict)
    """
    canonical = {}      # canonical_pk → record
    quarantine = []

    def process_rows(rows, source_name, is_authoritative):
        for row_num, raw in rows:
            rec = copy.deepcopy(raw)

            # Get and canonicalize own PK
            raw_pk = rec.get(pk_field)
            if not raw_pk:
                quarantine.append(quarantine_record(
                    rec, entity_type, source_name, row_num, source_file,
                    f"Missing PK field '{pk_field}'", pk_field
                ))
                continue

            canonical_pk, err = try_canonicalize_id(str(raw_pk))
            if err:
                quarantine.append(quarantine_record(
                    rec, entity_type, source_name, row_num, source_file,
                    f"Cannot canonicalize PK: {err}", pk_field
                ))
                continue

            # Update PK to canonical
            rec[pk_field] = canonical_pk

            # Canonicalize FK fields
            fk_error = False
            for fk_field in fk_fields:
                raw_fk = rec.get(fk_field)
                if raw_fk and str(raw_fk).strip():
                    canonical_fk, fk_err = try_canonicalize_id(str(raw_fk))
                    if fk_err:
                        # FK canonicalization failure is non-fatal:
                        # quarantine but still try to proceed if possible
                        quarantine.append(quarantine_record(
                            rec, entity_type, source_name, row_num, source_file,
                            f"Cannot canonicalize FK '{fk_field}': {fk_err}", fk_field
                        ))
                        fk_error = True
                        break
                    rec[fk_field] = canonical_fk

            if fk_error:
                continue

            # Build lineage
            rec["_lineage"] = make_lineage(
                source=source_name,
                source_record_id=str(raw_pk),   # original noisy ID preserved here
                source_file_id=source_file,
                row_number=row_num,
            )

            # Deduplication: synthetic wins over noisy on same canonical PK
            if canonical_pk not in canonical:
                canonical[canonical_pk] = rec
            elif is_authoritative:
                # Synthetic re-writes noisy
                canonical[canonical_pk] = rec

    # Process synthetic first (authoritative), then noisy (adds new records only)
    process_rows(rows_synth, synth_source_name, is_authoritative=True)
    process_rows(rows_noisy, noisy_source_name, is_authoritative=False)

    return canonical, quarantine


# ── Per-entity normalization ───────────────────────────────────────────────

def normalize_merchants(stats, quarantine_all):
    rows_s = load_jsonl(os.path.join(RAW_SYNTH, "merchants.jsonl"))
    rows_n = load_jsonl(os.path.join(RAW_NOISY,  "merchants.jsonl"))
    canon, quar = normalize_entity(
        rows_s, rows_n, "merchant", "merchant_id", [],
        "SYNTHETIC_MERCHANT", "NOISY_MERCHANT", "merchants.jsonl"
    )
    quarantine_all.extend(quar)
    result = list(canon.values())
    write_jsonl(result, os.path.join(NORMALIZED, "merchants.jsonl"))
    stats["merchants"] = len(result)
    print(f"  merchants:          {len(rows_s):>5} synth + {len(rows_n):>5} noisy → {len(result):>5} canonical ({len(quar)} quarantined)")
    return {r["merchant_id"]: r for r in result}


def normalize_customers(merchant_ids, stats, quarantine_all):
    rows_s = load_jsonl(os.path.join(RAW_SYNTH, "customers.jsonl"))
    rows_n = load_jsonl(os.path.join(RAW_NOISY,  "customers.jsonl"))
    canon, quar = normalize_entity(
        rows_s, rows_n, "customer", "customer_id", ["merchant_id"],
        "SYNTHETIC_CUSTOMER", "NOISY_CUSTOMER", "customers.jsonl"
    )
    # Validate merchant FK
    valid = {}
    for pk, rec in canon.items():
        if rec.get("merchant_id") not in merchant_ids:
            quarantine_all.append(quarantine_record(
                rec, "customer", rec["_lineage"]["source"], 0, "customers.jsonl",
                f"FK merchant_id={rec.get('merchant_id')!r} not in merchants", "merchant_id"
            ))
        else:
            valid[pk] = rec
    quarantine_all.extend(quar)
    result = list(valid.values())
    write_jsonl(result, os.path.join(NORMALIZED, "customers.jsonl"))
    stats["customers"] = len(result)
    print(f"  customers:          {len(rows_s):>5} synth + {len(rows_n):>5} noisy → {len(result):>5} canonical ({len(quar)} quarantined)")
    return {r["customer_id"]: r for r in result}


def normalize_orders(merchant_ids, customer_ids, stats, quarantine_all):
    rows_s = load_jsonl(os.path.join(RAW_SYNTH, "orders.jsonl"))
    rows_n = load_jsonl(os.path.join(RAW_NOISY,  "orders.jsonl"))
    canon, quar = normalize_entity(
        rows_s, rows_n, "order", "order_id", ["merchant_id", "customer_id"],
        "SYNTHETIC_ORDER", "NOISY_ORDER", "orders.jsonl"
    )
    quarantine_all.extend(quar)
    result = list(canon.values())
    write_jsonl(result, os.path.join(NORMALIZED, "orders.jsonl"))
    stats["orders"] = len(result)
    print(f"  orders:             {len(rows_s):>5} synth + {len(rows_n):>5} noisy → {len(result):>5} canonical ({len(quar)} quarantined)")
    return {r["order_id"]: r for r in result}


def normalize_invoices(order_ids, merchant_ids, customer_ids, stats, quarantine_all):
    rows_s = load_jsonl(os.path.join(RAW_SYNTH, "invoices.jsonl"))
    rows_n = load_jsonl(os.path.join(RAW_NOISY,  "invoices.jsonl"))
    canon, quar = normalize_entity(
        rows_s, rows_n, "invoice", "invoice_id",
        ["order_id", "merchant_id", "customer_id"],
        "SYNTHETIC_INVOICE", "NOISY_INVOICE", "invoices.jsonl"
    )
    # Validate order FK (soft: quarantine missing orders)
    valid = {}
    for pk, rec in canon.items():
        oid = rec.get("order_id")
        if oid and oid not in order_ids:
            quarantine_all.append(quarantine_record(
                rec, "invoice", rec["_lineage"]["source"], 0, "invoices.jsonl",
                f"FK order_id={oid!r} not found in canonical orders", "order_id"
            ))
        else:
            valid[pk] = rec
    quarantine_all.extend(quar)
    result = list(valid.values())
    write_jsonl(result, os.path.join(NORMALIZED, "invoices.jsonl"))
    stats["invoices"] = len(result)
    print(f"  invoices:           {len(rows_s):>5} synth + {len(rows_n):>5} noisy → {len(result):>5} canonical ({len(quar)+len(canon)-len(valid)} quarantined)")
    return {r["invoice_id"]: r for r in result}


def normalize_payments(order_ids, merchant_ids, customer_ids, stats, quarantine_all):
    rows_s = load_jsonl(os.path.join(RAW_SYNTH, "payments.jsonl"))
    rows_n = load_jsonl(os.path.join(RAW_NOISY,  "payments.jsonl"))
    canon, quar = normalize_entity(
        rows_s, rows_n, "payment", "payment_id",
        ["order_id", "merchant_id", "customer_id"],
        "SYNTHETIC_PAYMENT", "NOISY_PAYMENT", "payments.jsonl"
    )
    # Validate order FK
    valid = {}
    for pk, rec in canon.items():
        oid = rec.get("order_id")
        if oid and oid not in order_ids:
            quarantine_all.append(quarantine_record(
                rec, "payment", rec["_lineage"]["source"], 0, "payments.jsonl",
                f"FK order_id={oid!r} not found in canonical orders", "order_id"
            ))
        else:
            valid[pk] = rec
    quarantine_all.extend(quar)
    result = list(valid.values())
    write_jsonl(result, os.path.join(NORMALIZED, "payments.jsonl"))
    stats["payments"] = len(result)
    print(f"  payments:           {len(rows_s):>5} synth + {len(rows_n):>5} noisy → {len(result):>5} canonical ({len(quar)+len(canon)-len(valid)} quarantined)")
    return {r["payment_id"]: r for r in result}


def normalize_fees(payment_ids, merchant_ids, stats, quarantine_all):
    rows_s = load_jsonl(os.path.join(RAW_SYNTH, "fees.jsonl"))
    rows_n = load_jsonl(os.path.join(RAW_NOISY,  "fees.jsonl"))
    canon, quar = normalize_entity(
        rows_s, rows_n, "fee", "fee_id",
        ["payment_id", "merchant_id"],
        "SYNTHETIC_FEE", "NOISY_FEE", "fees.jsonl"
    )
    valid = {}
    for pk, rec in canon.items():
        pid = rec.get("payment_id")
        if pid and pid not in payment_ids:
            quarantine_all.append(quarantine_record(
                rec, "fee", rec["_lineage"]["source"], 0, "fees.jsonl",
                f"FK payment_id={pid!r} not found in canonical payments", "payment_id"
            ))
        else:
            valid[pk] = rec
    quarantine_all.extend(quar)
    result = list(valid.values())
    write_jsonl(result, os.path.join(NORMALIZED, "fees.jsonl"))
    stats["fees"] = len(result)
    print(f"  fees:               {len(rows_s):>5} synth + {len(rows_n):>5} noisy → {len(result):>5} canonical ({len(quar)+len(canon)-len(valid)} quarantined)")
    return {r["fee_id"]: r for r in result}


def normalize_refunds(payment_ids, order_ids, merchant_ids, stats, quarantine_all):
    rows_s = load_jsonl(os.path.join(RAW_SYNTH, "refunds.jsonl"))
    rows_n = load_jsonl(os.path.join(RAW_NOISY,  "refunds.jsonl"))
    canon, quar = normalize_entity(
        rows_s, rows_n, "refund", "refund_id",
        ["payment_id", "order_id", "merchant_id"],
        "SYNTHETIC_REFUND", "NOISY_REFUND", "refunds.jsonl"
    )
    valid = {}
    for pk, rec in canon.items():
        pid = rec.get("payment_id")
        oid = rec.get("order_id")
        ok = True
        if pid and pid not in payment_ids:
            quarantine_all.append(quarantine_record(
                rec, "refund", rec["_lineage"]["source"], 0, "refunds.jsonl",
                f"FK payment_id={pid!r} not found", "payment_id"
            ))
            ok = False
        elif oid and oid not in order_ids:
            quarantine_all.append(quarantine_record(
                rec, "refund", rec["_lineage"]["source"], 0, "refunds.jsonl",
                f"FK order_id={oid!r} not found", "order_id"
            ))
            ok = False
        if ok:
            valid[pk] = rec
    quarantine_all.extend(quar)
    result = list(valid.values())
    write_jsonl(result, os.path.join(NORMALIZED, "refunds.jsonl"))
    stats["refunds"] = len(result)
    print(f"  refunds:            {len(rows_s):>5} synth + {len(rows_n):>5} noisy → {len(result):>5} canonical ({len(quar)+len(canon)-len(valid)} quarantined)")
    return {r["refund_id"]: r for r in result}


def normalize_settlements(merchant_ids, stats, quarantine_all):
    rows_s = load_jsonl(os.path.join(RAW_SYNTH, "settlements.jsonl"))
    rows_n = load_jsonl(os.path.join(RAW_NOISY,  "settlements.jsonl"))
    # Also check filesystem quarantine (15 known quarantined settlements)
    quar_file = os.path.join(RAW_NOISY, "quarantine_settlements.jsonl")
    quarantined_already = load_jsonl(quar_file)

    canon, quar = normalize_entity(
        rows_s, rows_n, "settlement", "settlement_id",
        ["merchant_id"],
        "SYNTHETIC_SETTLEMENT", "NOISY_SETTLEMENT", "settlements.jsonl"
    )
    quarantine_all.extend(quar)
    # Add already-quarantined settlements to quarantine output
    for _, qr in quarantined_already:
        quarantine_all.append({
            "quarantined_at": INGESTED_AT,
            "entity_type": "settlement",
            "source": "QUARANTINE_FS",
            "source_file": "quarantine_settlements.jsonl",
            "source_row": 0,
            "reason": qr.get("reason", "pre-existing filesystem quarantine"),
            "failed_field": None,
            "raw_record": qr,
        })
    result = list(canon.values())
    write_jsonl(result, os.path.join(NORMALIZED, "settlements.jsonl"))
    stats["settlements"] = len(result)
    print(f"  settlements:        {len(rows_s):>5} synth + {len(rows_n):>5} noisy → {len(result):>5} canonical ({len(quar)} quarantined, {len(quarantined_already)} pre-existing quarantine)")
    return {r["settlement_id"]: r for r in result}


def normalize_settlement_payments(payment_ids, settlement_ids, stats, quarantine_all):
    """Load from synthetic (ground truth of settlement-payment links)."""
    rows_s = load_jsonl(os.path.join(RAW_SYNTH, "settlement_payments.jsonl"))
    rows_n = load_jsonl(os.path.join(RAW_NOISY,  "settlement_payments.jsonl"))

    seen = set()
    result = []
    quar_count = 0

    for row_num, raw in rows_s + rows_n:
        rec = copy.deepcopy(raw)
        src = "SYNTHETIC_STL_PAY" if (row_num, raw) in [(r, d) for r, d in rows_s] else "NOISY_STL_PAY"

        # Canonicalize both FK fields
        stl_id_raw = rec.get("settlement_id")
        pay_id_raw = rec.get("payment_id")

        if not stl_id_raw or not pay_id_raw:
            quar_count += 1
            continue

        stl_id, err1 = try_canonicalize_id(str(stl_id_raw))
        pay_id, err2 = try_canonicalize_id(str(pay_id_raw))

        if err1 or err2:
            quar_count += 1
            quarantine_all.append(quarantine_record(
                rec, "settlement_payment", "SETTLEMENT_PAYMENT", row_num, "settlement_payments.jsonl",
                f"Cannot canonicalize: stl={err1}, pay={err2}", None
            ))
            continue

        # Validate FKs
        if stl_id not in settlement_ids:
            quarantine_all.append(quarantine_record(
                rec, "settlement_payment", "SETTLEMENT_PAYMENT", row_num, "settlement_payments.jsonl",
                f"FK settlement_id={stl_id!r} not found", "settlement_id"
            ))
            quar_count += 1
            continue
        if pay_id not in payment_ids:
            quarantine_all.append(quarantine_record(
                rec, "settlement_payment", "SETTLEMENT_PAYMENT", row_num, "settlement_payments.jsonl",
                f"FK payment_id={pay_id!r} not found", "payment_id"
            ))
            quar_count += 1
            continue

        # Dedup
        pair_key = (stl_id, pay_id)
        if pair_key in seen:
            continue
        seen.add(pair_key)

        rec["settlement_id"] = stl_id
        rec["payment_id"] = pay_id
        rec["_lineage"] = make_lineage("SYNTHETIC_STL_PAY", f"{stl_id}:{pay_id}",
                                       "settlement_payments.jsonl", row_num)
        result.append(rec)

    write_jsonl(result, os.path.join(NORMALIZED, "settlement_payments.jsonl"))
    stats["settlement_payments"] = len(result)
    print(f"  settlement_payments:{len(rows_s):>5} synth + {len(rows_n):>5} noisy → {len(result):>5} canonical ({quar_count} quarantined)")
    return result


def normalize_bank_records(settlement_ids, merchant_ids, stats, quarantine_all):
    rows_s = load_jsonl(os.path.join(RAW_SYNTH, "bank_records.jsonl"))
    rows_n = load_jsonl(os.path.join(RAW_NOISY,  "bank_records.jsonl"))
    canon, quar = normalize_entity(
        rows_s, rows_n, "bank_record", "bank_record_id",
        ["settlement_id", "merchant_id"],
        "SYNTHETIC_BANK", "NOISY_BANK", "bank_records.jsonl"
    )
    # Soft validation on settlement_id (may be legitimately missing due to missing records corruption)
    quarantine_all.extend(quar)
    valid = {}
    for pk, rec in canon.items():
        sid = rec.get("settlement_id")
        if sid and sid not in settlement_ids:
            # This is intentional noisy case (wrong_references corruption) — keep but note
            rec["_note"] = f"settlement_id={sid!r} not in canonical settlements (expected noisy corruption)"
        valid[pk] = rec
    result = list(valid.values())
    write_jsonl(result, os.path.join(NORMALIZED, "bank_records.jsonl"))
    stats["bank_records"] = len(result)
    print(f"  bank_records:       {len(rows_s):>5} synth + {len(rows_n):>5} noisy → {len(result):>5} canonical ({len(quar)} quarantined)")
    return {r["bank_record_id"]: r for r in result}


def normalize_books(merchant_ids, stats, quarantine_all):
    rows_s = load_jsonl(os.path.join(RAW_SYNTH, "books.jsonl"))
    rows_n = load_jsonl(os.path.join(RAW_NOISY,  "books.jsonl"))
    canon, quar = normalize_entity(
        rows_s, rows_n, "book_entry", "entry_id",
        ["merchant_id"],
        "SYNTHETIC_BOOK", "NOISY_BOOK", "books.jsonl"
    )
    quarantine_all.extend(quar)
    result = list(canon.values())
    write_jsonl(result, os.path.join(NORMALIZED, "books.jsonl"))
    stats["books"] = len(result)
    print(f"  books:              {len(rows_s):>5} synth + {len(rows_n):>5} noisy → {len(result):>5} canonical ({len(quar)} quarantined)")
    return result


def normalize_gst_records(invoice_ids, merchant_ids, stats, quarantine_all):
    rows_s = load_jsonl(os.path.join(RAW_SYNTH, "gst_records.jsonl"))
    rows_n = load_jsonl(os.path.join(RAW_NOISY,  "gst_records.jsonl"))
    canon, quar = normalize_entity(
        rows_s, rows_n, "gst_record", "gst_record_id",
        ["invoice_id", "merchant_id"],
        "SYNTHETIC_GST", "NOISY_GST", "gst_records.jsonl"
    )
    valid = {}
    for pk, rec in canon.items():
        iid = rec.get("invoice_id")
        if iid and iid not in invoice_ids:
            quarantine_all.append(quarantine_record(
                rec, "gst_record", rec["_lineage"]["source"], 0, "gst_records.jsonl",
                f"FK invoice_id={iid!r} not found in canonical invoices", "invoice_id"
            ))
        else:
            valid[pk] = rec
    quarantine_all.extend(quar)
    result = list(valid.values())
    write_jsonl(result, os.path.join(NORMALIZED, "gst_records.jsonl"))
    stats["gst_records"] = len(result)
    print(f"  gst_records:        {len(rows_s):>5} synth + {len(rows_n):>5} noisy → {len(result):>5} canonical ({len(quar)+len(canon)-len(valid)} quarantined)")
    return result


def normalize_adjustments(settlement_ids, merchant_ids, stats, quarantine_all):
    rows_s = load_jsonl(os.path.join(RAW_SYNTH, "adjustments.jsonl"))
    rows_n = load_jsonl(os.path.join(RAW_NOISY,  "adjustments.jsonl"))
    canon, quar = normalize_entity(
        rows_s, rows_n, "adjustment", "adjustment_id",
        ["settlement_id", "merchant_id"],
        "SYNTHETIC_ADJ", "NOISY_ADJ", "adjustments.jsonl"
    )
    valid = {}
    for pk, rec in canon.items():
        sid = rec.get("settlement_id")
        if sid and sid not in settlement_ids:
            quarantine_all.append(quarantine_record(
                rec, "adjustment", rec["_lineage"]["source"], 0, "adjustments.jsonl",
                f"FK settlement_id={sid!r} not found", "settlement_id"
            ))
        else:
            valid[pk] = rec
    quarantine_all.extend(quar)
    result = list(valid.values())
    write_jsonl(result, os.path.join(NORMALIZED, "adjustments.jsonl"))
    stats["adjustments"] = len(result)
    print(f"  adjustments:        {len(rows_s):>5} synth + {len(rows_n):>5} noisy → {len(result):>5} canonical ({len(quar)+len(canon)-len(valid)} quarantined)")
    return result


# ── Main pipeline ──────────────────────────────────────────────────────────

def run_normalization(dry_run: bool = False) -> dict:
    """
    Run the full canonical normalization pipeline.
    Returns stats dict.
    """
    print("=" * 70)
    print("  CANONICAL NORMALIZATION PIPELINE v2.0.0")
    print("=" * 70)
    print(f"\n  Source (synthetic): {RAW_SYNTH}")
    print(f"  Source (noisy):     {RAW_NOISY}")
    print(f"  Output:             {NORMALIZED}")
    print(f"  Dry run:            {dry_run}\n")

    if dry_run:
        print("  [DRY RUN - no files will be written]\n")
        return {}

    os.makedirs(NORMALIZED, exist_ok=True)
    os.makedirs(QUARANTINE_DIR, exist_ok=True)

    stats = {}
    quarantine_all = []

    print("  Normalizing in dependency order...")
    print(f"  {'Entity':<25} {'Source'}")
    print(f"  {'-'*25} {'-'*45}")

    # Dependency order
    merchants  = normalize_merchants(stats, quarantine_all)
    customers  = normalize_customers(set(merchants.keys()), stats, quarantine_all)
    orders     = normalize_orders(set(merchants.keys()), set(customers.keys()), stats, quarantine_all)
    invoices   = normalize_invoices(set(orders.keys()), set(merchants.keys()), set(customers.keys()), stats, quarantine_all)
    payments   = normalize_payments(set(orders.keys()), set(merchants.keys()), set(customers.keys()), stats, quarantine_all)
    fees       = normalize_fees(set(payments.keys()), set(merchants.keys()), stats, quarantine_all)
    refunds    = normalize_refunds(set(payments.keys()), set(orders.keys()), set(merchants.keys()), stats, quarantine_all)
    settlements = normalize_settlements(set(merchants.keys()), stats, quarantine_all)
    sp         = normalize_settlement_payments(set(payments.keys()), set(settlements.keys()), stats, quarantine_all)
    bank_recs  = normalize_bank_records(set(settlements.keys()), set(merchants.keys()), stats, quarantine_all)
    books      = normalize_books(set(merchants.keys()), stats, quarantine_all)
    gst        = normalize_gst_records(set(invoices.keys()), set(merchants.keys()), stats, quarantine_all)
    adj        = normalize_adjustments(set(settlements.keys()), set(merchants.keys()), stats, quarantine_all)

    # Write quarantine file
    quarantine_path = os.path.join(QUARANTINE_DIR, "quarantine_canonical.jsonl")
    write_jsonl(quarantine_all, quarantine_path)
    stats["quarantine"] = len(quarantine_all)

    # Summary
    print("\n" + "=" * 70)
    print("  NORMALIZATION COMPLETE")
    print("=" * 70)
    print(f"\n  {'Entity':<28} {'Records':>8}")
    print(f"  {'-'*28} {'-'*8}")
    for entity, count in stats.items():
        if entity != "quarantine":
            print(f"  {entity:<28} {count:>8,}")
    total = sum(v for k, v in stats.items() if k != "quarantine")
    print(f"  {'TOTAL':<28} {total:>8,}")
    print(f"\n  Quarantined records: {stats.get('quarantine', 0)}")
    print(f"  Quarantine file:     {quarantine_path}")

    return stats


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Canonical normalization pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Do not write output files")
    args = parser.parse_args()
    run_normalization(dry_run=args.dry_run)
