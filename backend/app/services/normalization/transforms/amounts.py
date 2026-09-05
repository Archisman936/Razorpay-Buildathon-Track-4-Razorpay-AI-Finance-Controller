"""
Amount Normalization — Step 8

Converts all amount representations to Decimal("X.XX").

Rules:
- Remove currency symbols (₹, Rs., INR, $, etc.)
- Remove thousands separators (,)
- Standardize decimal precision to 2 places
- Reject malformed numeric values (quarantine, don't default to 0)
- Never use float as authoritative financial type

CRITICAL: missing amount ≠ amount=0. Return None for missing.
"""

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

# Currency symbols and prefixes to strip
CURRENCY_PATTERNS = [
    r"₹",
    r"Rs\.?\s*",
    r"INR\s*",
    r"\$",
    r"€",
    r"£",
    r"¥",
    r"USD\s*",
    r"EUR\s*",
]

TWO_PLACES = Decimal("0.01")


def normalize_amount(raw_value) -> Optional[Decimal]:
    """
    Normalize a raw amount value to Decimal.

    Returns None if value is missing/None (not 0).
    Raises ValueError if value is present but unparseable.

    Examples:
        "₹5,000"     → Decimal("5000.00")
        "Rs. 5000"   → Decimal("5000.00")
        "INR 5,000.00" → Decimal("5000.00")
        "5000"       → Decimal("5000.00")
        "-200.50"    → Decimal("-200.50")
        None         → None  (missing, not zero)
        ""           → None  (missing, not zero)
        "₹10O0"      → raises ValueError (OCR error)
    """
    # Missing value — return None explicitly
    if raw_value is None:
        return None

    raw = str(raw_value).strip()

    if raw == "" or raw.lower() in ("null", "none", "n/a", "-"):
        return None

    # Strip currency symbols/prefixes
    cleaned = raw
    for pattern in CURRENCY_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Remove thousands separators (commas) — but only if they're separators
    # Pattern: comma followed by exactly 3 digits (not decimal comma)
    # Simple approach: remove all commas, then validate
    cleaned = cleaned.replace(",", "")

    # Remove trailing/leading whitespace
    cleaned = cleaned.strip()

    # At this point should be a valid number: optional minus, digits, optional decimal
    if not re.match(r"^-?\d+(\.\d+)?$", cleaned):
        raise ValueError(
            f"Cannot parse '{raw}' as a valid amount. "
            f"Cleaned form '{cleaned}' is not numeric."
        )

    try:
        amount = Decimal(cleaned).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ValueError(f"Decimal conversion failed for '{raw}'")

    return amount


def normalize_amount_safe(raw_value, field_name: str = "amount") -> tuple:
    """
    Safe wrapper — returns (Decimal_or_None, error_message_or_None).

    Use this when you want to quarantine rather than raise.
    """
    try:
        result = normalize_amount(raw_value)
        return result, None
    except ValueError as e:
        return None, str(e)


def format_amount(amount: Optional[Decimal]) -> Optional[str]:
    """
    Convert Decimal back to canonical string representation for JSON/DB.

    Example: Decimal("5000.00") → "5000.00"
    """
    if amount is None:
        return None
    return str(amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


def amounts_approximately_equal(a: Decimal, b: Decimal,
                                 tolerance_pct: Decimal = Decimal("0.02"),
                                 tolerance_abs: Decimal = Decimal("1.00")) -> bool:
    """
    Check if two amounts are approximately equal within tolerance.

    Uses: |a - b| / max(a, b) <= tolerance_pct  OR  |a - b| <= tolerance_abs

    Used by reconciliation engine — NOT by normalization itself.
    Normalization always preserves actual values.
    """
    if a is None or b is None:
        return False
    diff = abs(a - b)
    max_val = max(abs(a), abs(b))
    if max_val == 0:
        return diff == 0
    pct_diff = diff / max_val
    return pct_diff <= tolerance_pct or diff <= tolerance_abs
