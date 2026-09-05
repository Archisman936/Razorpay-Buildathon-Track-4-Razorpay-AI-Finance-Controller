"""
Currency Normalization — Step 10

Converts all currency representations to ISO 4217 3-letter codes.

Examples:
    "₹"    → "INR"
    "Rs."  → "INR"
    "rs"   → "INR"
    "inr"  → "INR"
    "$"    → "USD"
    "usd"  → "USD"
"""

from typing import Optional

# Symbol/alias → ISO 4217 code
CURRENCY_MAP = {
    # Indian Rupee
    "₹": "INR",
    "rs": "INR",
    "rs.": "INR",
    "inr": "INR",
    "rupee": "INR",
    "rupees": "INR",
    "indian rupee": "INR",

    # US Dollar
    "$": "USD",
    "usd": "USD",
    "us dollar": "USD",
    "dollar": "USD",

    # Euro
    "€": "EUR",
    "eur": "EUR",
    "euro": "EUR",

    # British Pound
    "£": "GBP",
    "gbp": "GBP",
    "pound": "GBP",
    "sterling": "GBP",

    # Japanese Yen
    "¥": "JPY",
    "jpy": "JPY",
    "yen": "JPY",
}

# All valid ISO 4217 codes we accept (extend as needed)
VALID_CURRENCY_CODES = {"INR", "USD", "EUR", "GBP", "JPY", "AED", "SGD", "AUD"}


def normalize_currency(raw_value: str, default: str = "INR") -> str:
    """
    Normalize currency to ISO 4217 3-letter code.

    Args:
        raw_value: Currency symbol, abbreviation, or name
        default: Default currency if value is missing (for this project: INR)

    Returns:
        ISO 4217 currency code string (e.g. "INR")

    Raises:
        ValueError if value is present but unrecognized
    """
    if not raw_value:
        return default

    key = str(raw_value).strip().lower()

    if key in CURRENCY_MAP:
        return CURRENCY_MAP[key]

    # Already a valid ISO code (case-insensitive check)
    upper = key.upper()
    if upper in VALID_CURRENCY_CODES:
        return upper

    raise ValueError(
        f"Unrecognized currency '{raw_value}'. "
        f"Add it to CURRENCY_MAP if it is valid."
    )


def normalize_currency_safe(raw_value: str, default: str = "INR") -> tuple:
    """
    Safe wrapper — returns (currency_code, error_or_None).
    """
    try:
        return normalize_currency(raw_value, default), None
    except ValueError as e:
        return default, str(e)
