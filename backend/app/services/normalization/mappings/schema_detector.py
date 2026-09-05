"""
Source Schema Detection — Step 3

Determines which source schema a raw record belongs to.
This drives which field mapping to apply.

Source schemas:
  SYNTHETIC_PAYMENT    - Generated JSONL from our pipeline
  SYNTHETIC_ORDER      - Generated JSONL from our pipeline
  SYNTHETIC_INVOICE    - Generated JSONL from our pipeline
  SYNTHETIC_SETTLEMENT - Generated JSONL from our pipeline
  SYNTHETIC_BANK       - Generated JSONL from our pipeline
  SYNTHETIC_BOOK       - Generated JSONL from our pipeline
  SYNTHETIC_GST        - Generated JSONL from our pipeline
  SYNTHETIC_FEE        - Generated JSONL from our pipeline
  SYNTHETIC_REFUND     - Generated JSONL from our pipeline
  SYNTHETIC_ADJUSTMENT - Generated JSONL from our pipeline
  RAZORPAY_PAYMENT     - Razorpay API/webhook
  RAZORPAY_SETTLEMENT  - Razorpay settlement report
  BANK_STATEMENT_CSV   - Bank CSV statement
  INVOICE_PDF          - Invoice PDF
  GST_PORTAL           - GST portal export
  TALLY_EXPORT         - Tally books export
  UNKNOWN              - Unrecognized
"""

from typing import Optional


# ── Fingerprinting rules ────────────────────────────────────────────────────
# Each rule is: (schema_name, required_fields, identifier_field_hint)
# Checked in priority order

SCHEMA_FINGERPRINTS = [
    # Synthetic JSONL schemas — detected by their stable ID field
    ("SYNTHETIC_PAYMENT",    {"payment_id", "order_id", "gateway"},             "payment_id"),
    ("SYNTHETIC_ORDER",      {"order_id", "merchant_id", "total_amount"},       "order_id"),
    ("SYNTHETIC_INVOICE",    {"invoice_id", "order_id", "invoice_number"},      "invoice_id"),
    ("SYNTHETIC_SETTLEMENT", {"settlement_id", "gross_amount", "net_amount"},   "settlement_id"),
    ("SYNTHETIC_BANK",       {"bank_record_id", "transaction_date", "balance_after"}, "bank_record_id"),
    ("SYNTHETIC_BOOK",       {"entry_id", "account_code", "debit", "credit"},   "entry_id"),
    ("SYNTHETIC_GST",        {"gst_record_id", "seller_gstin", "filing_period"},"gst_record_id"),
    ("SYNTHETIC_FEE",        {"fee_id", "fee_amount", "tax_amount"},            "fee_id"),
    ("SYNTHETIC_REFUND",     {"refund_id", "refund_amount", "refund_type"},     "refund_id"),
    ("SYNTHETIC_ADJUSTMENT", {"adjustment_id", "adjustment_type"},              "adjustment_id"),
    ("SYNTHETIC_MERCHANT",   {"merchant_id", "gstin", "bank_ifsc"},             "merchant_id"),
    ("SYNTHETIC_CUSTOMER",   {"customer_id", "merchant_id", "email"},           "customer_id"),

    # Razorpay API schemas
    ("RAZORPAY_PAYMENT",     {"id", "entity", "amount", "currency", "method"},  "id"),
    ("RAZORPAY_SETTLEMENT",  {"id", "entity", "amount", "fees", "tax"},         "id"),
    ("RAZORPAY_REFUND",      {"id", "entity", "amount", "payment_id"},          "id"),

    # Webhook
    ("RAZORPAY_WEBHOOK",     {"event", "payload", "entity"},                    None),

    # Bank statement (CSV-derived)
    ("BANK_STATEMENT_CSV",   {"transaction_date", "description", "amount", "balance"}, None),
    ("BANK_STATEMENT_CSV",   {"date", "narration", "debit", "credit", "balance"},      None),

    # GST portal
    ("GST_PORTAL",           {"gstin", "return_period", "taxable_value"},       None),
]


def detect_schema(record: dict) -> str:
    """
    Detect the source schema of a raw record by field fingerprinting.

    Args:
        record: Raw parsed record dict

    Returns:
        Schema name string (e.g. "SYNTHETIC_PAYMENT")
    """
    record_keys = set(record.keys())

    for schema_name, required_fields, _ in SCHEMA_FINGERPRINTS:
        if required_fields.issubset(record_keys):
            return schema_name

    return "UNKNOWN"


def detect_schema_from_filename(filename: str) -> Optional[str]:
    """
    Fallback schema detection from the JSONL filename.

    Used when the record itself has ambiguous fields.
    """
    name = filename.lower().replace("-", "_")
    mappings = {
        "payment": "SYNTHETIC_PAYMENT",
        "order": "SYNTHETIC_ORDER",
        "invoice": "SYNTHETIC_INVOICE",
        "settlement": "SYNTHETIC_SETTLEMENT",
        "bank_record": "SYNTHETIC_BANK",
        "book": "SYNTHETIC_BOOK",
        "gst_record": "SYNTHETIC_GST",
        "fee": "SYNTHETIC_FEE",
        "refund": "SYNTHETIC_REFUND",
        "adjustment": "SYNTHETIC_ADJUSTMENT",
        "merchant": "SYNTHETIC_MERCHANT",
        "customer": "SYNTHETIC_CUSTOMER",
    }
    for keyword, schema in mappings.items():
        if keyword in name:
            return schema
    return None
