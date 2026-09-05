"""
Text Normalization — Step 6

Normalizes free-text fields: names, descriptions, narrations, addresses.

Rules:
- Unicode NFKC normalization
- Strip leading/trailing whitespace
- Collapse repeated whitespace
- Normalize punctuation/separators
- Lowercase for canonical form
- Always preserve original value separately
"""

import unicodedata
import re


def normalize_text(value: str) -> str:
    """
    Full text normalization for merchant names, descriptions, narrations.

    Does NOT destroy original — caller should store original before calling.

    Args:
        value: Raw text string

    Returns:
        Cleaned canonical string (lowercase, collapsed whitespace, normalized)
    """
    if value is None:
        return ""

    # 1. Unicode NFKC normalization (decomposes ₹ → Rs, ligatures, etc.)
    value = unicodedata.normalize("NFKC", str(value))

    # 2. Lowercase
    value = value.lower()

    # 3. Normalize common separators → space
    #    Replace: -, /, \, _, |, . with space (but keep . inside numbers)
    value = re.sub(r"[-/\\|_]", " ", value)

    # 4. Strip currency symbols that may have snuck into text fields
    value = re.sub(r"[₹$€£¥]", "", value)

    # 5. Normalize punctuation — remove commas, colons, semicolons, quotes
    value = re.sub(r"[,;:\"'`]", "", value)

    # 6. Collapse repeated whitespace
    value = re.sub(r"\s+", " ", value)

    # 7. Strip leading/trailing whitespace
    value = value.strip()

    return value


def normalize_bank_narration(narration: str) -> str:
    """
    Specialized normalization for bank narration / description fields.

    More aggressive cleaning for fuzzy matching purposes.

    Example:
        "  RAZORPAY-SETTLEMENT / STL_001  " → "razorpay settlement stl 001"
    """
    if narration is None:
        return ""

    text = normalize_text(narration)

    # Remove common bank prefixes that add noise but not meaning
    noise_prefixes = [
        r"^neft\s+", r"^rtgs\s+", r"^imps\s+", r"^upi\s+",
        r"^cr\s+", r"^dr\s+", r"^trf\s+",
    ]
    for pattern in noise_prefixes:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Collapse again after removal
    text = re.sub(r"\s+", " ", text).strip()

    return text


def normalize_name(name: str) -> str:
    """
    Normalize person or business names.

    Example:
        "  shopease india pvt. ltd.  " → "shopease india pvt ltd"
    """
    if name is None:
        return ""

    text = normalize_text(name)

    # Remove trailing honorifics and legal suffixes noise
    text = re.sub(r"\bpvt\b\.?", "pvt", text)
    text = re.sub(r"\bltd\b\.?", "ltd", text)
    text = re.sub(r"\bllp\b\.?", "llp", text)

    return text.strip()


def normalize_gstin(gstin: str) -> str:
    """
    Normalize GSTIN: uppercase, strip spaces/hyphens.

    Indian GSTIN format: 15 alphanumeric characters.
    """
    if gstin is None:
        return ""
    return re.sub(r"[\s\-]", "", str(gstin)).upper()


def is_empty(value) -> bool:
    """Return True if value is None, empty string, or whitespace only."""
    if value is None:
        return True
    return str(value).strip() == ""
