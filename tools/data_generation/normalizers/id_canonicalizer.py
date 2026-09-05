"""
ID Canonicalization Utility — Phase 1
=======================================
Maps any noisy/variant entity ID format back to the canonical form.

The corruption engine (generator/corruption/id_noise.py) applies 5 strategies:
  DASH_SEPARATOR   → ORD-000123
  NO_SEPARATOR     → ORD000123
  SLASH_SEPARATOR  → ORD/000123
  LOWERCASE        → ord_000123
  PREFIX_VARIATION → ORDER_000123, ORDER000123, O_000123, O-000123

This utility extracts the numeric suffix and reconstructs the canonical ID.

Canonical format: {PREFIX}_{ZERO_PADDED_NUMBER}

Prefix mappings (canonical → all known variants):
  ORD → ORDER, O
  INV → INVOICE, I
  PAY → PAYMENT, P
  STL → SETTLEMENT, S
  FEE → FEE, F
  REF → REFUND, R
  GST → GST, G
  ADJ → ADJUSTMENT, A
  BNK → BANK, B
  LED → LEDGER, L
  MER → MERCHANT, M
  CUS → CUSTOMER, C
  STL_PAY → (no variant prefix)

Usage:
    from generator.normalizers.id_canonicalizer import canonicalize_id, CanonicalizeError

    canonical = canonicalize_id("ORD-000123")  # → "ORD_000123"
    canonical = canonicalize_id("ord_000123")  # → "ORD_000123"
    canonical = canonicalize_id("ORDER000123") # → "ORD_000123"
"""

import re
from typing import Optional, Tuple

# Separator characters used by corruption engine
_SEPARATORS = r"[-_/]?"

# All prefix variants → canonical prefix + zero-pad width
# Format: (pattern, canonical_prefix, zero_pad)
_PREFIX_RULES = [
    # Orders
    (r"^(?:ORDER|ORD|O)",   "ORD", 6),
    # Invoices
    (r"^(?:INVOICE|INV|I)", "INV", 6),
    # Payments
    (r"^(?:PAYMENT|PAY|P)", "PAY", 6),
    # Settlements
    (r"^(?:SETTLEMENT|STL|S)", "STL", 6),
    # Fees
    (r"^(?:FEE|F)",         "FEE", 6),
    # Refunds
    (r"^(?:REFUND|REF|R)",  "REF", 6),
    # GST records
    (r"^(?:GST|G)",         "GST", 6),
    # Adjustments
    (r"^(?:ADJUSTMENT|ADJ|A)", "ADJ", 6),
    # Bank records
    (r"^(?:BANK|BNK|B)",    "BNK", 6),
    # Book/Ledger entries
    (r"^(?:LEDGER|LED|L)",  "LED", 6),
    # Merchants
    (r"^(?:MERCHANT|MER|M)", "MER", 6),
    # Customers
    (r"^(?:CUSTOMER|CUS|C)", "CUS", 6),
]

# Pre-compiled full regex for each prefix rule
# Pattern: ^PREFIX[SEP?]DIGITS$  (case-insensitive)
_COMPILED_RULES = []
for (prefix_pattern, canonical, pad) in _PREFIX_RULES:
    full_pattern = re.compile(
        prefix_pattern + _SEPARATORS + r"(\d+)$",
        re.IGNORECASE
    )
    _COMPILED_RULES.append((full_pattern, canonical, pad))


class CanonicalizeError(ValueError):
    """Raised when an ID cannot be safely canonicalized."""
    pass


def canonicalize_id(id_val: str, strict: bool = True) -> Optional[str]:
    """
    Map a noisy/variant entity ID to its canonical form.

    Args:
        id_val:  The raw ID string (e.g., "ORD-000123", "inv_000005", "P000031")
        strict:  If True, raise CanonicalizeError for unrecognized IDs.
                 If False, return None for unrecognized IDs.

    Returns:
        Canonical ID string (e.g., "ORD_000123") or None if strict=False and unrecognized.

    Raises:
        CanonicalizeError: If strict=True and the ID cannot be canonicalized.
    """
    if not id_val or not isinstance(id_val, str):
        if strict:
            raise CanonicalizeError(f"ID is empty or not a string: {id_val!r}")
        return None

    id_stripped = id_val.strip()
    if not id_stripped:
        if strict:
            raise CanonicalizeError(f"ID is blank: {id_val!r}")
        return None

    for pattern, canonical_prefix, pad in _COMPILED_RULES:
        m = pattern.match(id_stripped)
        if m:
            number = m.group(1).lstrip("0") or "0"
            return f"{canonical_prefix}_{int(number):0{pad}d}"

    # Unrecognized format
    if strict:
        raise CanonicalizeError(
            f"Cannot canonicalize ID {id_val!r}: does not match any known entity prefix pattern."
        )
    return None


def try_canonicalize_id(id_val: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempt canonicalization; return (canonical, error_message).

    Returns:
        (canonical_id, None)   on success
        (None, error_message)  on failure
    """
    try:
        return canonicalize_id(id_val, strict=True), None
    except CanonicalizeError as e:
        return None, str(e)


def canonicalize_record(record: dict, pk_field: str, fk_fields: list) -> Tuple[dict, list]:
    """
    Canonicalize the PK and all specified FK fields in a record.
    Preserves original IDs in _lineage.source_record_id.

    Args:
        record:    The record dict (may contain _lineage nested dict)
        pk_field:  The primary key field name
        fk_fields: List of FK field names to canonicalize

    Returns:
        (updated_record, errors)
        errors is a list of (field_name, original_val, error_message) tuples
    """
    import copy
    rec = copy.deepcopy(record)
    errors = []

    # Canonicalize own PK
    original_pk = rec.get(pk_field)
    if original_pk:
        canonical_pk, err = try_canonicalize_id(str(original_pk))
        if err:
            errors.append((pk_field, original_pk, err))
        else:
            rec[pk_field] = canonical_pk
            # Preserve original in lineage
            if "_lineage" not in rec:
                rec["_lineage"] = {}
            if not rec["_lineage"].get("source_record_id"):
                rec["_lineage"]["source_record_id"] = str(original_pk)

    # Canonicalize FK fields
    for fk_field in fk_fields:
        original_fk = rec.get(fk_field)
        if original_fk and str(original_fk).strip():
            canonical_fk, err = try_canonicalize_id(str(original_fk))
            if err:
                errors.append((fk_field, original_fk, err))
            else:
                rec[fk_field] = canonical_fk

    return rec, errors


# ── Quick self-test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    TEST_CASES = [
        # (input, expected_output)
        ("ORD_000123", "ORD_000123"),
        ("ORD-000123", "ORD_000123"),
        ("ORD/000123", "ORD_000123"),
        ("ord_000123", "ORD_000123"),
        ("ord000123",  "ORD_000123"),
        ("ORD000123",  "ORD_000123"),
        ("ORDER_000123", "ORD_000123"),
        ("ORDER000123",  "ORD_000123"),
        ("O-000123",   "ORD_000123"),
        ("INV/000001", "INV_000001"),
        ("inv_000005", "INV_000005"),
        ("INV000030",  "INV_000030"),
        ("INV-001016", "INV_001016"),
        ("inv-000036", "INV_000036"),
        ("PAY000014",  "PAY_000014"),
        ("PAY/000020", "PAY_000020"),
        ("P-000006",   "PAY_000006"),
        ("P000638",    "PAY_000638"),
        ("pay_000031", "PAY_000031"),
        ("STL-000003", "STL_000003"),
        ("SETTLEMENT_000001", "STL_000001"),
        ("FEE_000001", "FEE_000001"),
        ("REF_000001", "REF_000001"),
        ("GST_000001", "GST_000001"),
        ("BNK_000001", "BNK_000001"),
        ("ADJ_000001", "ADJ_000001"),
        ("LED_000001", "LED_000001"),
        ("MER_000001", "MER_000001"),
        ("CUS_000001", "CUS_000001"),
        ("I_001545",   "INV_001545"),
        ("S_000003",   "STL_000003"),
    ]

    passed = 0
    failed = 0
    for (input_id, expected) in TEST_CASES:
        result = canonicalize_id(input_id, strict=False)
        status = "PASS" if result == expected else "FAIL"
        if status == "FAIL":
            print(f"  {status}: {input_id!r} -> {result!r} (expected {expected!r})")
            failed += 1
        else:
            passed += 1

    # Test error case
    try:
        canonicalize_id("RANDOMSTRING", strict=True)
        print("  FAIL: Should have raised CanonicalizeError for RANDOMSTRING")
        failed += 1
    except CanonicalizeError:
        passed += 1

    print(f"\nResults: {passed} passed, {failed} failed out of {len(TEST_CASES)+1} tests")
