"""
Bank Statement Field Mappings — Step 5 (Bank variant)

Maps bank CSV statement field names → canonical bank_record fields.

Different banks use different column names:
  HDFC:   Date, Narration, Chq./Ref.No., Value Dt, Withdrawal Amt., Deposit Amt., Closing Balance
  ICICI:  Transaction Date, Transaction Remarks, Amount (INR), Cr/Dr
  Axis:   Tran Date, Particulars, Debit, Credit, Balance
  SBI:    Txn Date, Description, Ref No./Cheque No., Debit, Credit, Balance
"""

# ── HDFC Bank CSV columns → canonical ────────────────────────────────────────
HDFC_BANK_MAP = {
    "Date":               "transaction_date",
    "Narration":          "description",
    "Chq./Ref.No.":       "reference",
    "Value Dt":           "value_date",
    "Withdrawal Amt.":    "debit_amount",
    "Deposit Amt.":       "credit_amount",
    "Closing Balance":    "balance_after",
}

# ── ICICI Bank CSV columns → canonical ───────────────────────────────────────
ICICI_BANK_MAP = {
    "Transaction Date":   "transaction_date",
    "Transaction Remarks":"description",
    "Ref No./Cheque No.": "reference",
    "Value Date":         "value_date",
    "Withdrawal Amount (INR)": "debit_amount",
    "Deposit Amount (INR)":    "credit_amount",
    "Balance (INR)":           "balance_after",
}

# ── Axis Bank CSV columns → canonical ────────────────────────────────────────
AXIS_BANK_MAP = {
    "Tran Date":          "transaction_date",
    "Particulars":        "description",
    "Chq No.":            "reference",
    "Debit":              "debit_amount",
    "Credit":             "credit_amount",
    "Balance":            "balance_after",
}

# ── SBI Bank CSV columns → canonical ─────────────────────────────────────────
SBI_BANK_MAP = {
    "Txn Date":           "transaction_date",
    "Description":        "description",
    "Ref No./Cheque No.": "reference",
    "Debit":              "debit_amount",
    "Credit":             "credit_amount",
    "Balance":            "balance_after",
}

# ── Generic/fallback bank mapping ─────────────────────────────────────────────
GENERIC_BANK_MAP = {
    # Date variants
    "date":               "transaction_date",
    "tran_date":          "transaction_date",
    "transaction_date":   "transaction_date",
    "value_date":         "value_date",
    # Description variants
    "narration":          "description",
    "particulars":        "description",
    "remarks":            "description",
    "description":        "description",
    "transaction_remarks":"description",
    # Amount variants
    "debit":              "debit_amount",
    "dr":                 "debit_amount",
    "withdrawal":         "debit_amount",
    "credit":             "credit_amount",
    "cr":                 "credit_amount",
    "deposit":            "credit_amount",
    "amount":             "amount",
    # Reference variants
    "reference":          "reference",
    "ref_no":             "reference",
    "chq_no":             "reference",
    "utr":                "utr",
    # Balance
    "balance":            "balance_after",
    "closing_balance":    "balance_after",
    "running_balance":    "balance_after",
}

ALL_BANK_MAPS = [HDFC_BANK_MAP, ICICI_BANK_MAP, AXIS_BANK_MAP, SBI_BANK_MAP]


def detect_bank_format(columns: list) -> str:
    """Detect which bank format a CSV uses by matching column sets."""
    col_set = set(c.strip() for c in columns)
    if "Narration" in col_set and "Withdrawal Amt." in col_set:
        return "HDFC"
    if "Transaction Remarks" in col_set:
        return "ICICI"
    if "Particulars" in col_set and "Tran Date" in col_set:
        return "AXIS"
    if "Txn Date" in col_set:
        return "SBI"
    return "GENERIC"


def get_bank_map(bank_format: str) -> dict:
    """Return the field map for a detected bank format."""
    maps = {
        "HDFC": HDFC_BANK_MAP,
        "ICICI": ICICI_BANK_MAP,
        "AXIS": AXIS_BANK_MAP,
        "SBI": SBI_BANK_MAP,
        "GENERIC": GENERIC_BANK_MAP,
    }
    return maps.get(bank_format, GENERIC_BANK_MAP)


def map_bank_record(raw: dict, bank_format: str = "GENERIC") -> dict:
    """
    Map a raw bank statement row to canonical bank_record fields.

    Also derives:
    - amount = credit_amount - debit_amount (signed)
    - transaction_type = CREDIT or DEBIT
    """
    from decimal import Decimal

    field_map = get_bank_map(bank_format)
    canonical = {}

    for raw_field, canon_field in field_map.items():
        # Try exact case match, then lowercase match
        if raw_field in raw:
            canonical[canon_field] = raw[raw_field]
        else:
            for k, v in raw.items():
                if k.strip().lower() == raw_field.lower():
                    canonical[canon_field] = v
                    break

    # Derive amount and transaction_type from debit/credit columns
    if "debit_amount" in canonical or "credit_amount" in canonical:
        debit = canonical.pop("debit_amount", None) or "0"
        credit = canonical.pop("credit_amount", None) or "0"
        try:
            d = Decimal(str(debit).replace(",", ""))
            c = Decimal(str(credit).replace(",", ""))
            if c > 0:
                canonical["amount"] = str(c)
                canonical["transaction_type"] = "CREDIT"
            else:
                canonical["amount"] = str(d)
                canonical["transaction_type"] = "DEBIT"
        except Exception:
            pass

    canonical["_source"] = f"BANK_STATEMENT_{bank_format}"
    canonical["_source_record_id"] = raw.get("reference", raw.get("Chq./Ref.No.", ""))
    return canonical
