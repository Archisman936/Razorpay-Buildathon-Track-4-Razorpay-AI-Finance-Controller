"""
Central Financial Rules Module.

Implements all financial equations from docs/FINANCIAL_RULES.md.
Every generator uses this module for calculations to ensure consistency.
"""

from decimal import Decimal, ROUND_HALF_UP
import yaml
import os

# ── Constants ────────────────────────────────────────────────────────────────

GST_RATE = Decimal("0.18")           # 18% GST
CGST_RATE = Decimal("0.09")          # 9% CGST (intra-state)
SGST_RATE = Decimal("0.09")          # 9% SGST (intra-state)
IGST_RATE = Decimal("0.18")          # 18% IGST (inter-state)
FEE_TAX_RATE = Decimal("0.18")       # 18% GST on fees

TWO_PLACES = Decimal("0.01")

# ── Fee Rules ────────────────────────────────────────────────────────────────

_fee_rules_cache = None

def load_fee_rules() -> dict:
    """Load fee rules from YAML config."""
    global _fee_rules_cache
    if _fee_rules_cache is not None:
        return _fee_rules_cache
    
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "config", "fee_rules.yaml"
    )
    with open(config_path, "r") as f:
        _fee_rules_cache = yaml.safe_load(f)
    return _fee_rules_cache


def get_payment_method_weights() -> dict:
    """Get payment method probability distribution."""
    rules = load_fee_rules()
    return rules["payment_method_distribution"]


# ── Rounding ─────────────────────────────────────────────────────────────────

def round_inr(amount: Decimal) -> Decimal:
    """Round to 2 decimal places (standard INR rounding)."""
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# ── Order Calculations ───────────────────────────────────────────────────────

def calc_order_amounts(subtotal: Decimal, discount_rate: Decimal,
                       seller_state: str, buyer_state: str) -> dict:
    """
    Calculate all order-level amounts.
    
    Returns dict with: discount, taxable_amount, cgst, sgst, igst, 
                       total_tax, total_amount
    """
    discount = round_inr(subtotal * discount_rate)
    taxable_amount = round_inr(subtotal - discount)
    
    if seller_state == buyer_state:
        cgst = round_inr(taxable_amount * CGST_RATE)
        sgst = round_inr(taxable_amount * SGST_RATE)
        igst = Decimal("0.00")
    else:
        cgst = Decimal("0.00")
        sgst = Decimal("0.00")
        igst = round_inr(taxable_amount * IGST_RATE)
    
    total_tax = cgst + sgst + igst
    total_amount = taxable_amount + total_tax
    
    return {
        "discount": discount,
        "taxable_amount": taxable_amount,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "total_tax": total_tax,
        "total_amount": total_amount,
    }


# ── Fee Calculations ────────────────────────────────────────────────────────

def calc_fee(payment_amount: Decimal, payment_method: str) -> dict:
    """
    Calculate fee for a payment based on payment method.
    
    Returns dict with: fee_amount, tax_amount, total_fee
    """
    rules = load_fee_rules()
    method_rules = rules["fee_rules"][payment_method]
    
    base_rate = Decimal(str(method_rules["base_rate"]))
    min_fee = Decimal(str(method_rules["min_fee"]))
    max_fee = Decimal(str(method_rules["max_fee"]))
    
    fee_amount = round_inr(payment_amount * base_rate)
    fee_amount = max(fee_amount, min_fee)
    fee_amount = min(fee_amount, max_fee)
    
    # For UPI with 0% rate, fee is 0
    if base_rate == Decimal("0"):
        fee_amount = Decimal("0.00")
    
    tax_amount = round_inr(fee_amount * FEE_TAX_RATE)
    total_fee = fee_amount + tax_amount
    
    return {
        "fee_amount": fee_amount,
        "tax_amount": tax_amount,
        "total_fee": total_fee,
    }


# ── Settlement Calculations ─────────────────────────────────────────────────

def calc_settlement_net(gross_amount: Decimal, total_fees: Decimal,
                        total_fee_tax: Decimal, total_refunds: Decimal,
                        total_adjustments: Decimal) -> Decimal:
    """
    Calculate net settlement amount.
    
    net = gross - fees - fee_tax - refunds + adjustments
    """
    net = gross_amount - total_fees - total_fee_tax - total_refunds + total_adjustments
    return round_inr(net)


# ── Refund Calculations ─────────────────────────────────────────────────────

def calc_refund_amount(payment_amount: Decimal, refund_type: str,
                       partial_fraction: Decimal = None) -> Decimal:
    """
    Calculate refund amount based on type.
    
    FULL: refund = payment amount
    PARTIAL: refund = payment × fraction
    REVERSAL: refund = payment amount (chargeback)
    """
    if refund_type == "FULL":
        return payment_amount
    elif refund_type == "PARTIAL":
        if partial_fraction is None:
            partial_fraction = Decimal("0.50")
        return round_inr(payment_amount * partial_fraction)
    elif refund_type == "REVERSAL":
        return payment_amount
    else:
        raise ValueError(f"Unknown refund type: {refund_type}")


# ── Accounting/Books Calculations ────────────────────────────────────────────

def create_double_entry(entry_date: str, merchant_id: str,
                        debit_account: str, debit_name: str,
                        credit_account: str, credit_name: str,
                        amount: Decimal, reference_type: str,
                        reference_id: str, description: str,
                        entry_type: str) -> list:
    """
    Create a balanced double-entry pair.
    
    Returns a list of two entry dicts (debit and credit).
    """
    base = {
        "merchant_id": merchant_id,
        "entry_date": entry_date,
        "reference_type": reference_type,
        "reference_id": reference_id,
        "description": description,
        "entry_type": entry_type,
    }
    
    debit_entry = {
        **base,
        "account_code": debit_account,
        "account_name": debit_name,
        "debit": str(amount),
        "credit": "0.00",
    }
    
    credit_entry = {
        **base,
        "account_code": credit_account,
        "account_name": credit_name,
        "debit": "0.00",
        "credit": str(amount),
    }
    
    return [debit_entry, credit_entry]


# ── Validation Helpers ───────────────────────────────────────────────────────

def validate_order_amounts(order: dict) -> bool:
    """Validate order total = taxable + tax."""
    taxable = Decimal(str(order["taxable_amount"]))
    tax = Decimal(str(order["total_tax"]))
    total = Decimal(str(order["total_amount"]))
    return total == taxable + tax


def validate_settlement_amounts(settlement: dict, fees: list,
                                 refunds: list, adjustments: list) -> bool:
    """Validate settlement net = gross - fees - fee_tax - refunds + adjustments."""
    gross = Decimal(str(settlement["gross_amount"]))
    total_fees = sum(Decimal(str(f["fee_amount"])) for f in fees)
    total_fee_tax = sum(Decimal(str(f["tax_amount"])) for f in fees)
    total_refunds_amt = sum(Decimal(str(r["refund_amount"])) for r in refunds)
    total_adj = sum(Decimal(str(a["amount"])) for a in adjustments)
    
    expected_net = calc_settlement_net(gross, total_fees, total_fee_tax,
                                       total_refunds_amt, total_adj)
    actual_net = Decimal(str(settlement["net_amount"]))
    
    return actual_net == expected_net


def validate_books_balance(entries: list, merchant_id: str) -> bool:
    """Validate total debits = total credits for a merchant."""
    total_debit = sum(Decimal(str(e["debit"])) for e in entries 
                      if e["merchant_id"] == merchant_id)
    total_credit = sum(Decimal(str(e["credit"])) for e in entries 
                       if e["merchant_id"] == merchant_id)
    return total_debit == total_credit
