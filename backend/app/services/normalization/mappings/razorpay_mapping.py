"""
Razorpay API Field Mappings — Step 5

Maps Razorpay API/webhook field names → canonical field names.

Razorpay uses: payment.id, payment.amount (in paise!), payment.method
Canonical uses: payment_id, amount (in rupees), payment_method
"""

# ── Razorpay Payment → Canonical Payment ─────────────────────────────────────
RAZORPAY_PAYMENT_MAP = {
    # Razorpay field      → canonical field
    "id":                   "payment_id",
    "order_id":             "order_id",
    "merchant_id":          "merchant_id",  # May not be in API response
    "amount":               "amount_paise",  # PAISE — must divide by 100!
    "currency":             "currency",
    "method":               "payment_method",
    "status":               "status",
    "captured":             "is_captured",
    "description":          "description",
    "email":                "customer_email",
    "contact":              "customer_phone",
    "created_at":           "created_at_unix",  # Unix timestamp
    "captured_at":          "captured_at_unix",
    "error_code":           "error_code",
    "error_description":    "error_description",
    "bank":                 "bank_name",
    "wallet":               "wallet_provider",
    "vpa":                  "upi_id",
    "card.name":            "card_holder_name",
    "card.network":         "card_network",
    "card.type":            "card_type",
    "card.last4":           "card_last4",
    "card.issuer":          "card_issuer",
    "acquirer_data.utr":    "utr",
    "acquirer_data.rrn":    "bank_reference",
}

# Fields requiring unit conversion (paise → rupees)
RAZORPAY_PAISE_FIELDS = {"amount_paise", "amount_refunded_paise"}

# Fields containing Unix timestamps (seconds since epoch)
RAZORPAY_UNIX_TS_FIELDS = {"created_at_unix", "captured_at_unix"}

# ── Razorpay Settlement → Canonical Settlement ────────────────────────────────
RAZORPAY_SETTLEMENT_MAP = {
    "id":               "settlement_id",
    "entity":           "_entity_type",
    "amount":           "net_amount_paise",
    "fees":             "total_fees_paise",
    "tax":              "total_fee_tax_paise",
    "utr":              "utr",
    "created_at":       "created_at_unix",
    "description":      "description",
}

# ── Razorpay Refund → Canonical Refund ───────────────────────────────────────
RAZORPAY_REFUND_MAP = {
    "id":               "refund_id",
    "entity":           "_entity_type",
    "amount":           "refund_amount_paise",
    "currency":         "currency",
    "payment_id":       "payment_id",
    "status":           "status",
    "speed_processed":  "speed",
    "notes":            "notes",
    "created_at":       "created_at_unix",
    "processed_at":     "refund_date_unix",
}

# ── Razorpay Webhook → entity extraction ─────────────────────────────────────
# Webhook structure: {"event": "payment.captured", "payload": {"payment": {"entity": {...}}}}
RAZORPAY_WEBHOOK_ENTITY_PATH = {
    "payment.captured":   ("payment", "entity"),
    "payment.failed":     ("payment", "entity"),
    "refund.created":     ("refund", "entity"),
    "settlement.processed": ("settlement", "entity"),
    "payment.authorized": ("payment", "entity"),
}


def flatten_razorpay_record(raw: dict, prefix: str = "") -> dict:
    """
    Flatten a nested Razorpay record into dot-notation keys.

    Example:
        {"card": {"network": "VISA", "last4": "4242"}}
        → {"card.network": "VISA", "card.last4": "4242"}
    """
    flat = {}
    for key, value in raw.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(flatten_razorpay_record(value, full_key))
        else:
            flat[full_key] = value
    return flat


def map_razorpay_payment(raw: dict) -> dict:
    """
    Map a Razorpay payment API record to canonical field names.

    Handles:
    - Paise → Rupees conversion (÷ 100)
    - Unix timestamp → ISO string
    - Nested card/UPI fields via dot notation
    """
    from decimal import Decimal
    from datetime import datetime, timezone

    flat = flatten_razorpay_record(raw)
    canonical = {}

    for rzp_field, canon_field in RAZORPAY_PAYMENT_MAP.items():
        if rzp_field in flat:
            value = flat[rzp_field]

            # Convert paise to rupees
            if canon_field in RAZORPAY_PAISE_FIELDS and value is not None:
                try:
                    value = str(Decimal(str(value)) / 100)
                except Exception:
                    pass

            # Convert Unix timestamp to ISO string
            if canon_field in RAZORPAY_UNIX_TS_FIELDS and value is not None:
                try:
                    dt = datetime.fromtimestamp(int(value), tz=timezone.utc)
                    value = dt.isoformat()
                except Exception:
                    pass

            canonical[canon_field] = value

    canonical["_source"] = "RAZORPAY_PAYMENT"
    canonical["_source_record_id"] = raw.get("id", "")
    return canonical


def map_razorpay_settlement(raw: dict) -> dict:
    """Map a Razorpay settlement API record to canonical fields."""
    from decimal import Decimal
    from datetime import datetime, timezone

    canonical = {}
    for rzp_field, canon_field in RAZORPAY_SETTLEMENT_MAP.items():
        if rzp_field in raw:
            value = raw[rzp_field]
            if "_paise" in canon_field and value is not None:
                try:
                    value = str(Decimal(str(value)) / 100)
                except Exception:
                    pass
            if "_unix" in canon_field and value is not None:
                try:
                    dt = datetime.fromtimestamp(int(value), tz=timezone.utc)
                    value = dt.isoformat()
                except Exception:
                    pass
            canonical[canon_field] = value

    canonical["_source"] = "RAZORPAY_SETTLEMENT"
    canonical["_source_record_id"] = raw.get("id", "")
    return canonical
