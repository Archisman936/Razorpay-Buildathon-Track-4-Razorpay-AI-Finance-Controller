"""
Entity-Specific Field Normalization — Step 12

Normalizes entity-specific fields that don't fit the generic transforms.
"""

import re
from typing import Optional

# ── Payment Method ────────────────────────────────────────────────────────────
PAYMENT_METHOD_MAP = {
    "upi": "UPI",
    "unified payments interface": "UPI",
    "card": "CARD",
    "credit card": "CARD",
    "debit card": "CARD",
    "netbanking": "NETBANKING",
    "net_banking": "NETBANKING",
    "net banking": "NETBANKING",
    "internet banking": "NETBANKING",
    "ib": "NETBANKING",
    "wallet": "WALLET",
    "e-wallet": "WALLET",
    "ewallet": "WALLET",
    "emi": "EMI",
    "buy_now_pay_later": "BNPL",
    "bnpl": "BNPL",
    "paylater": "BNPL",
}

# ── Card Type ─────────────────────────────────────────────────────────────────
CARD_TYPE_MAP = {
    "credit": "CREDIT",
    "credit card": "CREDIT",
    "debit": "DEBIT",
    "debit card": "DEBIT",
    "prepaid": "PREPAID",
    "corporate": "CORPORATE",
}

# ── Card Network ──────────────────────────────────────────────────────────────
CARD_NETWORK_MAP = {
    "visa": "VISA",
    "mastercard": "MASTERCARD",
    "master": "MASTERCARD",
    "mc": "MASTERCARD",
    "rupay": "RUPAY",
    "ru pay": "RUPAY",
    "amex": "AMEX",
    "american express": "AMEX",
    "maestro": "MAESTRO",
    "discover": "DISCOVER",
    "diners": "DINERS",
    "diners club": "DINERS",
}

# ── Book Entry Type ───────────────────────────────────────────────────────────
ENTRY_TYPE_MAP = {
    "sale": "SALE",
    "revenue": "SALE",
    "income": "SALE",
    "payment": "PAYMENT",
    "receipt": "PAYMENT",
    "fee": "FEE",
    "charge": "FEE",
    "commission": "FEE",
    "refund": "REFUND",
    "reversal": "REFUND",
    "settlement": "SETTLEMENT",
    "payout": "SETTLEMENT",
    "tax": "TAX",
    "gst": "TAX",
    "adjustment": "ADJUSTMENT",
    "correction": "ADJUSTMENT",
    "write_off": "ADJUSTMENT",
}

# ── Adjustment Type ───────────────────────────────────────────────────────────
ADJUSTMENT_TYPE_MAP = {
    "chargeback": "CHARGEBACK",
    "charge_back": "CHARGEBACK",
    "dispute": "CHARGEBACK",
    "rounding": "ROUNDING",
    "rounding_adjustment": "ROUNDING",
    "reversal": "REVERSAL",
    "reversed": "REVERSAL",
    "manual": "MANUAL_ADJUSTMENT",
    "manual_adjustment": "MANUAL_ADJUSTMENT",
    "settlement_adjustment": "SETTLEMENT_ADJUSTMENT",
}

# ── Supply Type (GST) ─────────────────────────────────────────────────────────
SUPPLY_TYPE_MAP = {
    "intra_state": "INTRA_STATE",
    "intra-state": "INTRA_STATE",
    "intrastate": "INTRA_STATE",
    "local": "INTRA_STATE",
    "inter_state": "INTER_STATE",
    "inter-state": "INTER_STATE",
    "interstate": "INTER_STATE",
    "central": "INTER_STATE",
}


def _normalize_enum(raw_value: str, enum_map: dict,
                    field_name: str, allow_unknown: bool = True) -> Optional[str]:
    """Generic enum normalizer."""
    if not raw_value:
        return None
    key = str(raw_value).strip().lower().replace("-", "_").replace(" ", "_")
    # Try exact key
    result = enum_map.get(key)
    if result:
        return result
    # Try without underscores
    result = enum_map.get(key.replace("_", ""))
    if result:
        return result
    if allow_unknown:
        return str(raw_value).upper()
    raise ValueError(f"Unrecognized {field_name} value: '{raw_value}'")


def normalize_payment_method(raw: str) -> Optional[str]:
    return _normalize_enum(raw, PAYMENT_METHOD_MAP, "payment_method")


def normalize_card_type(raw: str) -> Optional[str]:
    return _normalize_enum(raw, CARD_TYPE_MAP, "card_type")


def normalize_card_network(raw: str) -> Optional[str]:
    return _normalize_enum(raw, CARD_NETWORK_MAP, "card_network")


def normalize_entry_type(raw: str) -> Optional[str]:
    return _normalize_enum(raw, ENTRY_TYPE_MAP, "entry_type")


def normalize_adjustment_type(raw: str) -> Optional[str]:
    return _normalize_enum(raw, ADJUSTMENT_TYPE_MAP, "adjustment_type")


def normalize_supply_type(raw: str) -> Optional[str]:
    return _normalize_enum(raw, SUPPLY_TYPE_MAP, "supply_type")


def normalize_account_code(raw: str) -> Optional[str]:
    """Normalize chart of accounts code — strip whitespace, uppercase."""
    if not raw:
        return None
    return str(raw).strip().upper()


def normalize_return_type(raw: str) -> Optional[str]:
    """Normalize GST return type (GSTR-1, GSTR-3B, etc.)."""
    if not raw:
        return None
    return re.sub(r"\s+", "", str(raw)).upper()
