"""
Books/Ledger Generator — Step 18

Creates double-entry accounting entries for ALL financial events:
- Sales (orders)
- Payments received
- Fees charged
- Refunds processed
- Settlements received
- Tax entries

Output: data/raw/synthetic/books.jsonl
"""

import json
import os
import random
from decimal import Decimal
from datetime import datetime

from .financial_rules import round_inr

random.seed(42)

# ── Account Codes ────────────────────────────────────────────────────────────

ACCOUNTS = {
    "REVENUE":              {"code": "4000", "name": "Revenue"},
    "ACCOUNTS_RECEIVABLE":  {"code": "1200", "name": "Accounts Receivable"},
    "GST_PAYABLE":          {"code": "2100", "name": "GST Payable"},
    "CGST_PAYABLE":         {"code": "2101", "name": "CGST Payable"},
    "SGST_PAYABLE":         {"code": "2102", "name": "SGST Payable"},
    "IGST_PAYABLE":         {"code": "2103", "name": "IGST Payable"},
    "GATEWAY_RECEIVABLE":   {"code": "1210", "name": "Gateway Receivable"},
    "PROCESSING_FEE":       {"code": "5100", "name": "Payment Processing Fee"},
    "FEE_GST_INPUT":        {"code": "1300", "name": "GST Input Credit (Fees)"},
    "REFUND_EXPENSE":       {"code": "5200", "name": "Refund Expense"},
    "BANK_ACCOUNT":         {"code": "1100", "name": "Bank Account"},
    "ADJUSTMENT_INCOME":    {"code": "4100", "name": "Adjustment Income"},
    "ADJUSTMENT_EXPENSE":   {"code": "5300", "name": "Adjustment Expense"},
}


def _make_entry(entry_id: str, merchant_id: str, entry_date: str,
                account_key: str, debit: Decimal, credit: Decimal,
                reference_type: str, reference_id: str,
                description: str, entry_type: str) -> dict:
    """Create a single ledger entry."""
    acct = ACCOUNTS[account_key]
    return {
        "entry_id": entry_id,
        "merchant_id": merchant_id,
        "entry_date": entry_date,
        "account_code": acct["code"],
        "account_name": acct["name"],
        "debit": str(round_inr(debit)),
        "credit": str(round_inr(credit)),
        "reference_type": reference_type,
        "reference_id": reference_id,
        "description": description,
        "entry_type": entry_type,
    }


def generate_books(orders: list, payments: list, fees: list,
                   refunds: list, settlements: list,
                   output_dir: str) -> list:
    """
    Generate double-entry book/ledger entries for all financial events.
    
    Args:
        orders, payments, fees, refunds, settlements: Entity lists
        output_dir: Directory to write books.jsonl
    
    Returns:
        List of ledger entry dicts
    """
    entries = []
    entry_idx = 0
    
    # ── 1. Sale entries (from completed orders) ──────────────────────────
    
    for order in orders:
        if order["status"] != "COMPLETED":
            continue
        
        mid = order["merchant_id"]
        date = order["order_date"][:10]  # Just the date part
        total = Decimal(str(order["total_amount"]))
        taxable = Decimal(str(order["taxable_amount"]))
        cgst = Decimal(str(order["cgst"]))
        sgst = Decimal(str(order["sgst"]))
        igst = Decimal(str(order["igst"]))
        
        # Debit Accounts Receivable for total
        entry_idx += 1
        entries.append(_make_entry(
            f"LED_{entry_idx:06d}", mid, date,
            "ACCOUNTS_RECEIVABLE", total, Decimal("0"),
            "ORDER", order["order_id"],
            f"Sale - {order['order_id']}", "SALE"
        ))
        
        # Credit Revenue for taxable amount
        entry_idx += 1
        entries.append(_make_entry(
            f"LED_{entry_idx:06d}", mid, date,
            "REVENUE", Decimal("0"), taxable,
            "ORDER", order["order_id"],
            f"Revenue - {order['order_id']}", "SALE"
        ))
        
        # Credit GST Payable (split by type)
        if cgst > 0:
            entry_idx += 1
            entries.append(_make_entry(
                f"LED_{entry_idx:06d}", mid, date,
                "CGST_PAYABLE", Decimal("0"), cgst,
                "ORDER", order["order_id"],
                f"CGST on {order['order_id']}", "TAX"
            ))
        if sgst > 0:
            entry_idx += 1
            entries.append(_make_entry(
                f"LED_{entry_idx:06d}", mid, date,
                "SGST_PAYABLE", Decimal("0"), sgst,
                "ORDER", order["order_id"],
                f"SGST on {order['order_id']}", "TAX"
            ))
        if igst > 0:
            entry_idx += 1
            entries.append(_make_entry(
                f"LED_{entry_idx:06d}", mid, date,
                "IGST_PAYABLE", Decimal("0"), igst,
                "ORDER", order["order_id"],
                f"IGST on {order['order_id']}", "TAX"
            ))
    
    # ── 2. Payment entries ───────────────────────────────────────────────
    
    for payment in payments:
        if payment["status"] != "CAPTURED":
            continue
        
        mid = payment["merchant_id"]
        date = payment["payment_date"][:10]
        amount = Decimal(str(payment["amount"]))
        
        # Debit Gateway Receivable
        entry_idx += 1
        entries.append(_make_entry(
            f"LED_{entry_idx:06d}", mid, date,
            "GATEWAY_RECEIVABLE", amount, Decimal("0"),
            "PAYMENT", payment["payment_id"],
            f"Payment received - {payment['payment_id']}", "PAYMENT"
        ))
        
        # Credit Accounts Receivable
        entry_idx += 1
        entries.append(_make_entry(
            f"LED_{entry_idx:06d}", mid, date,
            "ACCOUNTS_RECEIVABLE", Decimal("0"), amount,
            "PAYMENT", payment["payment_id"],
            f"AR cleared - {payment['payment_id']}", "PAYMENT"
        ))
    
    # ── 3. Fee entries ───────────────────────────────────────────────────
    
    for fee in fees:
        fee_amount = Decimal(str(fee["fee_amount"]))
        tax_amount = Decimal(str(fee["tax_amount"]))
        
        if fee_amount <= 0:
            continue
        
        mid = fee["merchant_id"]
        # Use payment date if available
        payment_match = next((p for p in payments if p["payment_id"] == fee["payment_id"]), None)
        date = payment_match["payment_date"][:10] if payment_match else "2026-08-15"
        
        # Debit Processing Fee
        entry_idx += 1
        entries.append(_make_entry(
            f"LED_{entry_idx:06d}", mid, date,
            "PROCESSING_FEE", fee_amount, Decimal("0"),
            "FEE", fee["fee_id"],
            f"Gateway fee - {fee['fee_id']}", "FEE"
        ))
        
        # Debit Fee GST Input Credit
        if tax_amount > 0:
            entry_idx += 1
            entries.append(_make_entry(
                f"LED_{entry_idx:06d}", mid, date,
                "FEE_GST_INPUT", tax_amount, Decimal("0"),
                "FEE", fee["fee_id"],
                f"Fee GST input - {fee['fee_id']}", "FEE"
            ))
        
        # Credit Gateway Receivable for total fee
        total_fee = fee_amount + tax_amount
        entry_idx += 1
        entries.append(_make_entry(
            f"LED_{entry_idx:06d}", mid, date,
            "GATEWAY_RECEIVABLE", Decimal("0"), total_fee,
            "FEE", fee["fee_id"],
            f"Fee deducted - {fee['fee_id']}", "FEE"
        ))
    
    # ── 4. Refund entries ────────────────────────────────────────────────
    
    for refund in refunds:
        mid = refund["merchant_id"]
        date = refund["refund_date"][:10]
        amount = Decimal(str(refund["refund_amount"]))
        
        # Debit Refund Expense
        entry_idx += 1
        entries.append(_make_entry(
            f"LED_{entry_idx:06d}", mid, date,
            "REFUND_EXPENSE", amount, Decimal("0"),
            "REFUND", refund["refund_id"],
            f"Refund - {refund['refund_id']}", "REFUND"
        ))
        
        # Credit Gateway Receivable
        entry_idx += 1
        entries.append(_make_entry(
            f"LED_{entry_idx:06d}", mid, date,
            "GATEWAY_RECEIVABLE", Decimal("0"), amount,
            "REFUND", refund["refund_id"],
            f"Refund via gateway - {refund['refund_id']}", "REFUND"
        ))
    
    # ── 5. Settlement entries ────────────────────────────────────────────
    
    for settlement in settlements:
        mid = settlement["merchant_id"]
        date = settlement["settlement_date"][:10]
        net = Decimal(str(settlement["net_amount"]))
        
        # Debit Bank Account
        entry_idx += 1
        entries.append(_make_entry(
            f"LED_{entry_idx:06d}", mid, date,
            "BANK_ACCOUNT", net, Decimal("0"),
            "SETTLEMENT", settlement["settlement_id"],
            f"Settlement received - {settlement['settlement_id']}", "SETTLEMENT"
        ))
        
        # Credit Gateway Receivable
        entry_idx += 1
        entries.append(_make_entry(
            f"LED_{entry_idx:06d}", mid, date,
            "GATEWAY_RECEIVABLE", Decimal("0"), net,
            "SETTLEMENT", settlement["settlement_id"],
            f"Gateway settled - {settlement['settlement_id']}", "SETTLEMENT"
        ))
    
    # Write to JSONL
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "books.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    
    print(f"✓ Generated {len(entries)} book entries → {output_path}")
    return entries


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_dir = os.path.join(base_dir, "data", "raw", "synthetic")
    
    with open(os.path.join(data_dir, "orders.jsonl")) as f:
        orders = [json.loads(line) for line in f]
    with open(os.path.join(data_dir, "payments.jsonl")) as f:
        payments = [json.loads(line) for line in f]
    with open(os.path.join(data_dir, "fees.jsonl")) as f:
        fees = [json.loads(line) for line in f]
    with open(os.path.join(data_dir, "refunds.jsonl")) as f:
        refunds = [json.loads(line) for line in f]
    with open(os.path.join(data_dir, "settlements.jsonl")) as f:
        settlements = [json.loads(line) for line in f]
    
    generate_books(orders, payments, fees, refunds, settlements, data_dir)
