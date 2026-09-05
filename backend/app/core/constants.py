"""Shared reconciliation constants."""

from __future__ import annotations

PAIR_ORDER_PAYMENT = "ORDER_PAYMENT"
PAIR_ORDER_INVOICE = "ORDER_INVOICE"
PAIR_PAYMENT_FEE = "PAYMENT_FEE"
PAIR_PAYMENT_REFUND = "PAYMENT_REFUND"
PAIR_PAYMENT_SETTLEMENT = "PAYMENT_SETTLEMENT"
PAIR_SETTLEMENT_BANK = "SETTLEMENT_BANK"
PAIR_INVOICE_GST = "INVOICE_GST"
PAIR_EVENT_BOOKS = "EVENT_BOOKS"
PAIR_SETTLEMENT_ADJUSTMENT = "SETTLEMENT_ADJUSTMENT"

METHOD_DETERMINISTIC = "deterministic"
METHOD_ML = "ml"
METHOD_UNMATCHED = "unmatched"
METHOD_AMBIGUOUS = "ambiguous"

STATUS_MATCHED = "MATCHED_EXACT"
STATUS_MATCHED_DISCREPANCY = "MATCHED_WITH_DISCREPANCY"
STATUS_UNMATCHED = "UNMATCHED"
STATUS_AMBIGUOUS = "AMBIGUOUS"
STATUS_ML_MATCHED = "MATCHED_ML"

ENTITY_TYPE_CODES = {
    "order": "ORD",
    "orders": "ORD",
    "invoice": "INV",
    "invoices": "INV",
    "payment": "PAY",
    "payments": "PAY",
    "fee": "FEE",
    "fees": "FEE",
    "refund": "REF",
    "refunds": "REF",
    "settlement": "STL",
    "settlements": "STL",
    "bank": "BNK",
    "bank_record": "BNK",
    "bank_records": "BNK",
    "book": "LED",
    "books": "LED",
    "gst": "GST",
    "gst_records": "GST",
    "adjustment": "ADJ",
    "adjustments": "ADJ",
}

EXCEPTION_WHEN_STATUS = {
    STATUS_UNMATCHED,
    STATUS_AMBIGUOUS,
    STATUS_MATCHED_DISCREPANCY,
}
