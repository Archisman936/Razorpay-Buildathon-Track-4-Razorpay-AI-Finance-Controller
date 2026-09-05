"""
Status Normalization — Step 11

Maps source-specific status strings to canonical internal vocabulary.

Entity-specific because the same word can mean different things:
  "completed" in orders means a finished sale
  "completed" in settlements means funds disbursed

Internal canonical status vocabularies:
  Payment:    CAPTURED | FAILED | AUTHORIZED | REFUNDED | PENDING
  Order:      COMPLETED | CANCELLED | PENDING
  Settlement: SETTLED | PENDING | FAILED
  Refund:     PROCESSED | PENDING | FAILED
  Invoice:    ISSUED | PAID | CANCELLED | OVERDUE
  Bank:       CREDIT | DEBIT
  GST:        FILED | PENDING | REVISED
  Fee:        CHARGED | WAIVED
  Adjustment: APPLIED | REVERSED | PENDING
"""

from typing import Optional

# ── Payment Status ────────────────────────────────────────────────────────────
PAYMENT_STATUS_MAP = {
    # → CAPTURED (payment collected successfully)
    "captured": "CAPTURED",
    "paid": "CAPTURED",
    "success": "CAPTURED",
    "successful": "CAPTURED",
    "settled": "CAPTURED",
    "completed": "CAPTURED",
    "approved": "CAPTURED",

    # → FAILED
    "failed": "FAILED",
    "failure": "FAILED",
    "declined": "FAILED",
    "rejected": "FAILED",
    "error": "FAILED",
    "cancelled": "FAILED",
    "canceled": "FAILED",

    # → AUTHORIZED (hold placed, not yet captured)
    "authorized": "AUTHORIZED",
    "auth": "AUTHORIZED",
    "on_hold": "AUTHORIZED",

    # → REFUNDED
    "refunded": "REFUNDED",
    "reversed": "REFUNDED",
    "chargeback": "REFUNDED",

    # → PENDING
    "pending": "PENDING",
    "processing": "PENDING",
    "created": "PENDING",
    "initiated": "PENDING",
    "in_progress": "PENDING",
}

# ── Order Status ──────────────────────────────────────────────────────────────
ORDER_STATUS_MAP = {
    "completed": "COMPLETED",
    "complete": "COMPLETED",
    "confirmed": "COMPLETED",
    "delivered": "COMPLETED",
    "fulfilled": "COMPLETED",
    "cancelled": "CANCELLED",
    "canceled": "CANCELLED",
    "cancellation": "CANCELLED",
    "abandoned": "CANCELLED",
    "pending": "PENDING",
    "placed": "PENDING",
    "processing": "PENDING",
    "created": "PENDING",
}

# ── Settlement Status ─────────────────────────────────────────────────────────
SETTLEMENT_STATUS_MAP = {
    "settled": "SETTLED",
    "processed": "SETTLED",
    "completed": "SETTLED",
    "paid": "SETTLED",
    "pending": "PENDING",
    "processing": "PENDING",
    "initiated": "PENDING",
    "failed": "FAILED",
    "error": "FAILED",
    "rejected": "FAILED",
}

# ── Refund Status ─────────────────────────────────────────────────────────────
REFUND_STATUS_MAP = {
    "processed": "PROCESSED",
    "completed": "PROCESSED",
    "success": "PROCESSED",
    "successful": "PROCESSED",
    "paid": "PROCESSED",
    "pending": "PENDING",
    "initiated": "PENDING",
    "processing": "PENDING",
    "failed": "FAILED",
    "error": "FAILED",
    "rejected": "FAILED",
}

# ── Invoice Status ────────────────────────────────────────────────────────────
INVOICE_STATUS_MAP = {
    "issued": "ISSUED",
    "sent": "ISSUED",
    "generated": "ISSUED",
    "paid": "PAID",
    "settled": "PAID",
    "cleared": "PAID",
    "cancelled": "CANCELLED",
    "canceled": "CANCELLED",
    "voided": "CANCELLED",
    "overdue": "OVERDUE",
    "expired": "OVERDUE",
    "past_due": "OVERDUE",
}

# ── Bank Transaction Type ─────────────────────────────────────────────────────
BANK_TRANSACTION_TYPE_MAP = {
    "credit": "CREDIT",
    "cr": "CREDIT",
    "deposit": "CREDIT",
    "receipt": "CREDIT",
    "debit": "DEBIT",
    "dr": "DEBIT",
    "withdrawal": "DEBIT",
    "payment": "DEBIT",
}

# ── GST Status ────────────────────────────────────────────────────────────────
GST_STATUS_MAP = {
    "filed": "FILED",
    "submitted": "FILED",
    "pending": "PENDING",
    "due": "PENDING",
    "revised": "REVISED",
    "amended": "REVISED",
}


# ── Generic normalizer ────────────────────────────────────────────────────────
def normalize_status(raw_value: str, entity_type: str,
                     allow_unknown: bool = False) -> Optional[str]:
    """
    Normalize a status value for a given entity type.

    Args:
        raw_value: Raw status string from source
        entity_type: One of: payment, order, settlement, refund,
                              invoice, bank, gst, fee, adjustment
        allow_unknown: If True, return raw uppercase on no match;
                       if False, raise ValueError

    Returns:
        Canonical status string

    Raises:
        ValueError if unrecognized and allow_unknown=False
    """
    if not raw_value:
        return None

    key = str(raw_value).strip().lower().replace("-", "_").replace(" ", "_")

    status_maps = {
        "payment": PAYMENT_STATUS_MAP,
        "order": ORDER_STATUS_MAP,
        "settlement": SETTLEMENT_STATUS_MAP,
        "refund": REFUND_STATUS_MAP,
        "invoice": INVOICE_STATUS_MAP,
        "bank": BANK_TRANSACTION_TYPE_MAP,
        "gst": GST_STATUS_MAP,
    }

    status_map = status_maps.get(entity_type.lower())
    if status_map is None:
        if allow_unknown:
            return str(raw_value).upper()
        raise ValueError(f"Unknown entity_type '{entity_type}'")

    result = status_map.get(key)
    if result is not None:
        return result

    if allow_unknown:
        return str(raw_value).upper()

    raise ValueError(
        f"Unrecognized {entity_type} status '{raw_value}'. "
        f"Add it to the status map or set allow_unknown=True."
    )


def normalize_status_safe(raw_value: str, entity_type: str) -> tuple:
    """Safe wrapper — returns (canonical_status, error_or_None)."""
    try:
        return normalize_status(raw_value, entity_type, allow_unknown=True), None
    except ValueError as e:
        return None, str(e)
