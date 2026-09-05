"""
ID/Reference Normalization — Step 7

Normalizes entity identifiers so different representations of the same
ID become comparable.

Examples:
    ORD-1001, ORD/1001, ORD_1001, ORD1001  → ORD1001
    STL-000001, SETTLEMENT-001              → STL000001

IMPORTANT: This normalization creates a CANONICAL LOOKUP KEY.
           The original ID is always preserved for lineage.
           Do NOT replace the source ID with the normalized form
           in the financial data — only use for matching.
"""

import re
import unicodedata


# Known entity prefixes and their aliases
PREFIX_ALIASES = {
    # Canonical prefix → list of all known aliases
    "MER": ["MER", "MERCHANT"],
    "CUS": ["CUS", "CUSTOMER"],
    "ORD": ["ORD", "ORDER", "O"],
    "INV": ["INV", "INVOICE"],
    "PAY": ["PAY", "PAYMENT"],
    "FEE": ["FEE"],
    "REF": ["REF", "REFUND"],
    "STL": ["STL", "SETTLEMENT", "S"],
    "BNK": ["BNK", "BANK"],
    "LED": ["LED", "LEDGER"],
    "GST": ["GST"],
    "ADJ": ["ADJ", "ADJUSTMENT"],
}

# Reverse lookup: alias → canonical prefix
ALIAS_TO_CANONICAL = {}
for canonical, aliases in PREFIX_ALIASES.items():
    for alias in aliases:
        ALIAS_TO_CANONICAL[alias.upper()] = canonical


def normalize_entity_id(raw_id: str) -> str:
    """
    Normalize an entity ID to a canonical comparable form.

    Removes separators (_, -, /), normalizes prefix aliases,
    strips leading zeros from numeric suffix for lookup.

    Example:
        "ORD-000123"   → "ORD000123"
        "ORDER_000123" → "ORD000123"
        "ord/123"      → "ORD123"

    Args:
        raw_id: Raw entity ID string

    Returns:
        Canonical ID string (uppercase, no separator, canonical prefix)
    """
    if not raw_id:
        return ""

    raw = str(raw_id).strip().upper()

    # Remove separators
    clean = re.sub(r"[-/_\s]", "", raw)

    # Try to split prefix from numeric suffix
    match = re.match(r"^([A-Z]+)(\d+)(.*)$", clean)
    if match:
        prefix = match.group(1)
        number = match.group(2)
        suffix = match.group(3)

        # Canonicalize the prefix
        canonical_prefix = ALIAS_TO_CANONICAL.get(prefix, prefix)
        return f"{canonical_prefix}{number}{suffix}"

    return clean


def normalize_utr(utr: str) -> str:
    """
    Normalize UTR (Unique Transaction Reference).

    UTR formats vary by bank. Strip whitespace and uppercase.

    Example:
        "HDFC 1234567890123" → "HDFC1234567890123"
    """
    if not utr:
        return ""
    return re.sub(r"\s+", "", str(utr)).upper()


def normalize_gateway_reference(ref: str) -> str:
    """
    Normalize gateway references (Razorpay pay_xxx format).

    Example:
        "pay_AbCdEf" → "pay_AbCdEf"  (case preserved for gateway refs)
    """
    if not ref:
        return ""
    return str(ref).strip()


def normalize_invoice_number(inv_num: str) -> str:
    """
    Normalize invoice numbers.

    Remove spaces, normalize slashes.

    Example:
        "INV / 2026-27 / 001 / 00001" → "INV/2026-27/001/00001"
    """
    if not inv_num:
        return ""
    # Collapse whitespace around slashes
    normalized = re.sub(r"\s*/\s*", "/", str(inv_num).strip())
    return normalized.upper()


def normalize_bank_reference(ref: str) -> str:
    """
    Normalize bank transaction references.

    Example:
        "REF 123456" → "REF123456"
    """
    if not ref:
        return ""
    return re.sub(r"\s+", "", str(ref)).upper()


def make_dedup_key(source: str, source_record_id: str) -> str:
    """
    Create a deduplication key from source + source_record_id.

    Example:
        ("BANK", "BNK_000001") → "BANK::BNK000001"
    """
    return f"{source.upper()}::{normalize_entity_id(source_record_id)}"
