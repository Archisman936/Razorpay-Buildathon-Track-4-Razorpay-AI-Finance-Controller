"""
Financial Record Validation — Step 15

Validates normalized records before PostgreSQL insertion.

Checks:
1. Required fields present and non-null
2. Amounts non-negative where required
3. Financial equations balance
4. Enum values in canonical vocabulary

IMPORTANT: Validation failure → quarantine, not crash.
"""

from decimal import Decimal, InvalidOperation
from typing import Optional


TWO_PLACES = Decimal("0.01")
TOLERANCE = Decimal("0.02")  # 2 paisa tolerance for rounding


def _d(value) -> Optional[Decimal]:
    """Safe Decimal conversion."""
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(TWO_PLACES)
    except (InvalidOperation, TypeError):
        return None


def validate_order(record: dict) -> list:
    """Validate a canonical order record. Returns list of error strings."""
    errors = []
    required = ["order_id", "merchant_id", "customer_id",
                "total_amount", "taxable_amount", "total_tax", "currency"]
    for f in required:
        if not record.get(f):
            errors.append(f"MISSING_REQUIRED: {f}")

    total = _d(record.get("total_amount"))
    taxable = _d(record.get("taxable_amount"))
    tax = _d(record.get("total_tax"))
    cgst = _d(record.get("cgst", 0))
    sgst = _d(record.get("sgst", 0))
    igst = _d(record.get("igst", 0))

    if total is not None and total < 0:
        errors.append(f"NEGATIVE_AMOUNT: total_amount={total}")

    if total and taxable and tax:
        expected_total = taxable + tax
        if abs(total - expected_total) > TOLERANCE:
            errors.append(
                f"ARITHMETIC_FAIL: total={total} ≠ taxable({taxable}) + tax({tax})"
            )

    if tax and cgst is not None and sgst is not None and igst is not None:
        expected_tax = cgst + sgst + igst
        if abs(tax - expected_tax) > TOLERANCE:
            errors.append(
                f"ARITHMETIC_FAIL: total_tax={tax} ≠ cgst+sgst+igst={expected_tax}"
            )

    return errors


def validate_payment(record: dict) -> list:
    """Validate a canonical payment record."""
    errors = []
    required = ["payment_id", "order_id", "amount", "currency", "status"]
    for f in required:
        if not record.get(f):
            errors.append(f"MISSING_REQUIRED: {f}")

    amount = _d(record.get("amount"))
    if amount is not None and amount < 0:
        errors.append(f"NEGATIVE_AMOUNT: amount={amount}")

    valid_statuses = {"CAPTURED", "FAILED", "AUTHORIZED", "REFUNDED", "PENDING"}
    status = record.get("status", "")
    if status and status not in valid_statuses:
        errors.append(f"INVALID_STATUS: payment status '{status}' not in {valid_statuses}")

    return errors


def validate_invoice(record: dict) -> list:
    """Validate a canonical invoice record."""
    errors = []
    required = ["invoice_id", "order_id", "invoice_number",
                "total_amount", "taxable_amount", "currency"]
    for f in required:
        if not record.get(f):
            errors.append(f"MISSING_REQUIRED: {f}")

    total = _d(record.get("total_amount"))
    taxable = _d(record.get("taxable_amount"))
    tax = _d(record.get("total_tax"))

    if total and taxable and tax:
        expected = taxable + tax
        if abs(total - expected) > TOLERANCE:
            errors.append(
                f"ARITHMETIC_FAIL: total={total} ≠ taxable+tax={expected}"
            )

    return errors


def validate_settlement(record: dict) -> list:
    """
    Validate a canonical settlement record.

    Formula: net = gross - fees - fee_tax - refunds + adjustments
    """
    errors = []
    required = ["settlement_id", "merchant_id", "gross_amount", "net_amount", "currency"]
    for f in required:
        if not record.get(f):
            errors.append(f"MISSING_REQUIRED: {f}")

    gross = _d(record.get("gross_amount"))
    fees = _d(record.get("total_fees", 0))
    fee_tax = _d(record.get("total_fee_tax", 0))
    refunds = _d(record.get("total_refunds", 0))
    adjustments = _d(record.get("total_adjustments", 0))
    net = _d(record.get("net_amount"))

    if all(v is not None for v in [gross, fees, fee_tax, refunds, adjustments, net]):
        expected_net = gross - fees - fee_tax - refunds + adjustments
        if abs(net - expected_net) > TOLERANCE:
            errors.append(
                f"ARITHMETIC_FAIL: net={net} ≠ "
                f"gross({gross})-fees({fees})-fee_tax({fee_tax})"
                f"-refunds({refunds})+adj({adjustments})={expected_net}"
            )

    return errors


def validate_bank_record(record: dict) -> list:
    """Validate a canonical bank record."""
    errors = []
    required = ["bank_record_id", "merchant_id", "amount", "transaction_date", "currency"]
    for f in required:
        if not record.get(f):
            errors.append(f"MISSING_REQUIRED: {f}")

    amount = _d(record.get("amount"))
    if amount is not None and amount < 0:
        errors.append(f"NEGATIVE_AMOUNT: amount={amount}")

    tx_type = record.get("transaction_type", "")
    if tx_type and tx_type not in ("CREDIT", "DEBIT"):
        errors.append(f"INVALID_ENUM: transaction_type='{tx_type}'")

    return errors


def validate_book_entry(record: dict) -> list:
    """Validate a canonical book entry."""
    errors = []
    required = ["entry_id", "merchant_id", "entry_date", "account_code"]
    for f in required:
        if not record.get(f):
            errors.append(f"MISSING_REQUIRED: {f}")

    debit = _d(record.get("debit", 0))
    credit = _d(record.get("credit", 0))

    if debit is None and credit is None:
        errors.append("MISSING_REQUIRED: both debit and credit are missing")

    # One of debit/credit must be zero per entry (double-entry)
    if debit is not None and credit is not None:
        if debit > 0 and credit > 0:
            errors.append(
                f"INVALID_ENTRY: both debit={debit} and credit={credit} are positive"
            )

    return errors


def validate_fee(record: dict) -> list:
    """Validate a canonical fee record."""
    errors = []
    required = ["fee_id", "payment_id", "fee_amount", "tax_amount"]
    for f in required:
        if not record.get(f):
            errors.append(f"MISSING_REQUIRED: {f}")

    fee = _d(record.get("fee_amount"))
    tax = _d(record.get("tax_amount"))

    if fee is not None and tax is not None:
        expected_tax = (fee * Decimal("0.18")).quantize(TWO_PLACES)
        if abs(tax - expected_tax) > TOLERANCE:
            errors.append(
                f"ARITHMETIC_FAIL: tax={tax} ≠ fee*18%={expected_tax}"
            )

    return errors


ENTITY_VALIDATORS = {
    "order":      validate_order,
    "payment":    validate_payment,
    "invoice":    validate_invoice,
    "settlement": validate_settlement,
    "bank":       validate_bank_record,
    "book":       validate_book_entry,
    "fee":        validate_fee,
}


def validate_record(record: dict, entity_type: str) -> list:
    """
    Validate a canonical record for a given entity type.

    Returns:
        List of error strings (empty = valid)
    """
    validator = ENTITY_VALIDATORS.get(entity_type.lower())
    if validator is None:
        return []  # No validator defined — pass through
    return validator(record)
