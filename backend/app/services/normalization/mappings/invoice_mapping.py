"""
Invoice, GST, and Books Field Mappings — Step 5

Maps invoice, GST, and ledger source fields → canonical fields.
"""

# ── Invoice Mapping ───────────────────────────────────────────────────────────
# Handles variations from different accounting systems
INVOICE_FIELD_MAP = {
    # Canonical (our JSONL)
    "invoice_id":         "invoice_id",
    "invoice_number":     "invoice_number",
    "invoice_no":         "invoice_number",
    "inv_no":             "invoice_number",
    "invoice_date":       "invoice_date",
    "due_date":           "due_date",
    "order_id":           "order_id",
    "merchant_id":        "merchant_id",
    "customer_id":        "customer_id",
    "total_amount":       "total_amount",
    "subtotal":           "subtotal",
    "discount":           "discount",
    "taxable_amount":     "taxable_amount",
    "cgst":               "cgst",
    "sgst":               "sgst",
    "igst":               "igst",
    "total_tax":          "total_tax",
    "currency":           "currency",
    "seller_gstin":       "seller_gstin",
    "status":             "status",
    # Tally/Zoho/QuickBooks variants
    "inv_date":           "invoice_date",
    "bill_date":          "invoice_date",
    "bill_no":            "invoice_number",
    "total":              "total_amount",
    "net_amount":         "total_amount",
    "gstin":              "seller_gstin",
    "gst_no":             "seller_gstin",
    "tax_amount":         "total_tax",
}


def map_invoice_record(raw: dict) -> dict:
    """Map raw invoice record to canonical fields."""
    canonical = {}
    for raw_field, canon_field in INVOICE_FIELD_MAP.items():
        for k, v in raw.items():
            if k.strip().lower() == raw_field.lower():
                canonical[canon_field] = v
                break
    canonical["_source"] = raw.get("_source", "SYNTHETIC_INVOICE")
    canonical["_source_record_id"] = raw.get("invoice_id", raw.get("invoice_number", ""))
    return canonical


# ── GST Mapping ───────────────────────────────────────────────────────────────
GST_FIELD_MAP = {
    "gst_record_id":      "gst_record_id",
    "invoice_id":         "invoice_id",
    "invoice_number":     "invoice_number",
    "merchant_id":        "merchant_id",
    "seller_gstin":       "seller_gstin",
    "buyer_gstin":        "buyer_gstin",
    "supply_type":        "supply_type",
    "taxable_amount":     "taxable_amount",
    "cgst":               "cgst",
    "sgst":               "sgst",
    "igst":               "igst",
    "total_tax":          "total_tax",
    "total_amount":       "total_amount",
    "filing_period":      "filing_period",
    "return_type":        "return_type",
    "status":             "status",
    # GST portal export variants
    "gstin_of_supplier":  "seller_gstin",
    "gstin_of_recipient": "buyer_gstin",
    "taxable_value":      "taxable_amount",
    "integrated_tax":     "igst",
    "central_tax":        "cgst",
    "state_ut_tax":       "sgst",
    "return_period":      "filing_period",
}


def map_gst_record(raw: dict) -> dict:
    """Map raw GST record to canonical fields."""
    canonical = {}
    for raw_field, canon_field in GST_FIELD_MAP.items():
        for k, v in raw.items():
            if k.strip().lower() == raw_field.lower():
                canonical[canon_field] = v
                break
    canonical["_source"] = raw.get("_source", "SYNTHETIC_GST")
    canonical["_source_record_id"] = raw.get("gst_record_id", raw.get("invoice_number", ""))
    return canonical


# ── Books/Ledger Mapping ──────────────────────────────────────────────────────
BOOKS_FIELD_MAP = {
    "entry_id":           "entry_id",
    "merchant_id":        "merchant_id",
    "entry_date":         "entry_date",
    "account_code":       "account_code",
    "account_name":       "account_name",
    "debit":              "debit",
    "credit":             "credit",
    "reference_type":     "reference_type",
    "reference_id":       "reference_id",
    "description":        "description",
    "entry_type":         "entry_type",
    # Tally export variants
    "voucher_type":       "entry_type",
    "voucher_date":       "entry_date",
    "ledger_name":        "account_name",
    "dr_amount":          "debit",
    "cr_amount":          "credit",
    "narration":          "description",
}


def map_book_entry(raw: dict) -> dict:
    """Map raw book/ledger entry to canonical fields."""
    canonical = {}
    for raw_field, canon_field in BOOKS_FIELD_MAP.items():
        for k, v in raw.items():
            if k.strip().lower() == raw_field.lower():
                canonical[canon_field] = v
                break
    canonical["_source"] = raw.get("_source", "SYNTHETIC_BOOK")
    canonical["_source_record_id"] = raw.get("entry_id", "")
    return canonical
