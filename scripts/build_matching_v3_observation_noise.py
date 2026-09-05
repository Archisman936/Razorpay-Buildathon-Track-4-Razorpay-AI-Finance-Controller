"""
Matching v3 observation-noise layer.

Purpose:
    Create a matching-specific observed bank feed that is harder and more
    realistic than the original synthetic feed without modifying:
      - PostgreSQL / normalized data
      - data/raw/bank_records_raw.jsonl
      - ground truth
      - classification data

Key fixes vs v2:
    1. Extra noise is NOT conditioned on settlement_id or ground truth.
    2. Reference noise includes true observation/OCR/keying errors that
       survive normalize_id(), not only formatting changes that normalization
       would erase.
    3. Description noise masks settlement IDs from observed descriptions,
       preventing the true settlement_id from becoming a deterministic shortcut.
    4. Amount/date jitter is sampled independently per record.

All randomness is deterministic and seeded per record.
"""

import hashlib
import json
import random
import re
from datetime import timedelta

from common import load_table, parse_dt

SEED = 42
random.seed(SEED)

RAW_PATH = "data/raw/bank_records_raw.jsonl"
SETTLEMENTS_PATH = "data/normalized/settlements.jsonl"
OUTPUT_PATH = "scratch/matching_v3/bank_records_matching_observed.jsonl"


def seeded_rng(record_id, salt):
    h = hashlib.sha256(f"{record_id}:{salt}:{SEED}".encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def one_ref_error(value, rng):
    """Apply one plausible character-level observation error."""
    value = str(value)
    if not value:
        return value

    chars = list(value)
    operation = rng.choice(["substitute", "delete", "transpose", "duplicate"])

    if operation == "substitute":
        idx = rng.randrange(len(chars))
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        current = chars[idx].upper()
        choices = [c for c in alphabet if c != current]
        chars[idx] = rng.choice(choices)

    elif operation == "delete" and len(chars) > 4:
        idx = rng.randrange(1, len(chars) - 1)
        del chars[idx]

    elif operation == "transpose" and len(chars) > 5:
        idx = rng.randrange(1, len(chars) - 2)
        chars[idx], chars[idx + 1] = chars[idx + 1], chars[idx]

    elif operation == "duplicate":
        idx = rng.randrange(len(chars))
        chars.insert(idx, chars[idx])

    return "".join(chars)


def apply_reference_noise(value, rng):
    value = str(value or "")
    if not value:
        return value

    # Some records remain clean, most get a realistic observation error.
    u = rng.random()

    if u < 0.35:
        return value

    if u < 0.82:
        return one_ref_error(value, rng)

    # A minority receive two independent errors. This is still plausible
    # for OCR/keying/parsing noise and is important for avoiding a synthetic
    # perfect-similarity shortcut.
    out = one_ref_error(value, rng)
    out = one_ref_error(out, rng)
    return out


def mask_known_settlement_ids(description, settlement_ids):
    """Remove settlement IDs from observed descriptions without altering source data."""
    if not description:
        return description

    result = str(description)
    # Longest first avoids partial replacements where IDs share prefixes.
    for sid in sorted(settlement_ids, key=len, reverse=True):
        if sid:
            result = re.sub(
                re.escape(str(sid)),
                "SETTLEMENT",
                result,
                flags=re.IGNORECASE,
            )
    return result


# -------------------------------------------------------------------------
# Load the already-ground-truth-replayed raw bank feed as the starting layer.
# This file is READ ONLY.
# -------------------------------------------------------------------------
raw_bank = load_jsonl(RAW_PATH)
settlements = load_jsonl(SETTLEMENTS_PATH)
settlement_ids = [s.get("settlement_id", "") for s in settlements]

observed_bank = {}

reference_changed = 0
description_changed = 0
amount_changed = 0
date_changed = 0

for original in raw_bank:
    bid = original["bank_record_id"]
    rec = dict(original)

    # ------------------------------------------------------------------
    # Reference observation noise.
    # NOT conditioned on settlement_id / ground truth.
    # ------------------------------------------------------------------
    if rec.get("reference"):
        rng = seeded_rng(bid, "reference")
        original_value = str(rec["reference"])
        rec["reference"] = apply_reference_noise(original_value, rng)
        if rec["reference"] != original_value:
            reference_changed += 1

    # ------------------------------------------------------------------
    # Description observation noise.
    # First remove settlement IDs that could otherwise leak the target.
    # Then, for a substantial fraction of records, replace with a generic
    # bank-style narration. This trigger depends only on record ID.
    # ------------------------------------------------------------------
    if rec.get("description"):
        original_value = str(rec["description"])
        masked = mask_known_settlement_ids(
            original_value,
            settlement_ids,
        )

        rng = seeded_rng(bid, "description")
        generic = [
            "BANK TRANSFER CREDIT",
            "NEFT CREDIT",
            "ACCOUNT CREDIT",
            "ONLINE TRANSFER",
            "BANK CREDIT",
            "ELECTRONIC TRANSFER",
            "TRANSFER CREDIT",
        ]

        if rng.random() < 0.70:
            rec["description"] = rng.choice(generic)
        else:
            rec["description"] = masked

        if rec["description"] != original_value:
            description_changed += 1

    # ------------------------------------------------------------------
    # Extra amount observation noise.
    # Applied independently to any record with a parseable amount.
    # NOT conditioned on settlement linkage.
    # ------------------------------------------------------------------
    if rec.get("amount") is not None:
        rng = seeded_rng(bid, "amount")
        if rng.random() < 0.45:
            try:
                amount = float(rec["amount"])
                pct = rng.uniform(-0.025, 0.025)
                if abs(pct) >= 0.002:
                    new_amount = f"{amount * (1.0 + pct):.2f}"
                    if new_amount != str(rec["amount"]):
                        rec["amount"] = new_amount
                        amount_changed += 1
            except (TypeError, ValueError):
                pass

    # ------------------------------------------------------------------
    # Extra date observation noise.
    # Applied independently to any record with a parseable date.
    # NOT conditioned on settlement linkage.
    # ------------------------------------------------------------------
    if rec.get("transaction_date"):
        rng = seeded_rng(bid, "date")
        if rng.random() < 0.35:
            try:
                dt = parse_dt(rec["transaction_date"])
                if dt is not None:
                    shift = rng.choice([-3, -2, -1, 1, 2, 3])
                    rec["transaction_date"] = (
                        dt + timedelta(days=shift)
                    ).strftime("%Y-%m-%d")
                    date_changed += 1
            except Exception:
                pass

    observed_bank[bid] = rec


# -------------------------------------------------------------------------
# Deterministic output.
# -------------------------------------------------------------------------
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    for bid in sorted(observed_bank):
        f.write(json.dumps(observed_bank[bid], sort_keys=True) + "\n")

print(f"Observation-noise layer applied to {len(observed_bank)} bank records.")
print(f"  reference changed    : {reference_changed}")
print(f"  description changed  : {description_changed}")
print(f"  amount changed       : {amount_changed}")
print(f"  date changed         : {date_changed}")
print(f"Saved -> {OUTPUT_PATH}")
