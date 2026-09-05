"""
Settlement Generator — Step 16

Groups multiple payments into settlements.
NOT one settlement per payment — multiple payments map to one settlement.

Output: data/raw/synthetic/settlements.jsonl
        data/raw/synthetic/settlement_payments.jsonl
"""

import json
import os
import random
from decimal import Decimal
from datetime import datetime, timedelta
from collections import defaultdict

from .financial_rules import calc_settlement_net, round_inr

random.seed(42)

# ── Configuration ────────────────────────────────────────────────────────────

# How many payments per settlement (distribution)
PAYMENTS_PER_SETTLEMENT = [5, 6, 7, 8, 9, 10, 11, 12, 15, 20]

# Settlement happens T+1 to T+3 days after last payment
SETTLEMENT_DELAY_DAYS = (1, 3)


def generate_settlements(payments: list, fees: list, refunds: list,
                         output_dir: str) -> tuple:
    """
    Generate settlement records by grouping captured payments.
    
    Args:
        payments: List of payment dicts
        fees: List of fee dicts
        refunds: List of refund dicts
        output_dir: Directory to write settlements.jsonl and settlement_payments.jsonl
    
    Returns:
        Tuple of (settlements list, settlement_payments list)
    """
    # Only captured payments go into settlements
    captured_payments = [p for p in payments if p["status"] == "CAPTURED"]
    
    # Build lookup maps
    fee_by_payment = {}
    for f in fees:
        fee_by_payment[f["payment_id"]] = f
    
    refund_by_payment = defaultdict(list)
    for r in refunds:
        refund_by_payment[r["payment_id"]].append(r)
    
    # Group payments by merchant first (settlements are per-merchant)
    payments_by_merchant = defaultdict(list)
    for p in captured_payments:
        payments_by_merchant[p["merchant_id"]].append(p)
    
    # Sort each merchant's payments by date
    for mid in payments_by_merchant:
        payments_by_merchant[mid].sort(key=lambda p: p["payment_date"])
    
    settlements = []
    settlement_payments = []
    settlement_idx = 0
    
    for merchant_id, merchant_payments in payments_by_merchant.items():
        # Group into settlement batches
        remaining = list(merchant_payments)
        
        while remaining:
            batch_size = random.choice(PAYMENTS_PER_SETTLEMENT)
            batch_size = min(batch_size, len(remaining))
            batch = remaining[:batch_size]
            remaining = remaining[batch_size:]
            
            settlement_idx += 1
            settlement_id = f"STL_{settlement_idx:06d}"
            
            # Calculate settlement amounts
            gross_amount = Decimal("0.00")
            total_fees = Decimal("0.00")
            total_fee_tax = Decimal("0.00")
            total_refunds_amount = Decimal("0.00")
            
            for p in batch:
                gross_amount += Decimal(str(p["amount"]))
                
                fee = fee_by_payment.get(p["payment_id"])
                if fee:
                    total_fees += Decimal(str(fee["fee_amount"]))
                    total_fee_tax += Decimal(str(fee["tax_amount"]))
                
                for ref in refund_by_payment.get(p["payment_id"], []):
                    total_refunds_amount += Decimal(str(ref["refund_amount"]))
            
            # No adjustments yet (generated later)
            total_adjustments = Decimal("0.00")
            
            net_amount = calc_settlement_net(
                gross_amount, total_fees, total_fee_tax,
                total_refunds_amount, total_adjustments
            )
            
            # Settlement date = last payment date + delay
            last_payment_dt = max(
                datetime.fromisoformat(p["payment_date"].replace("+05:30", ""))
                for p in batch
            )
            delay = random.randint(*SETTLEMENT_DELAY_DAYS)
            settlement_dt = last_payment_dt + timedelta(days=delay)
            
            # Generate UTR for the settlement payout
            utr = f"UTIB{random.randint(10**12, 10**13 - 1)}"
            
            settlement = {
                "settlement_id": settlement_id,
                "merchant_id": merchant_id,
                "settlement_date": settlement_dt.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
                "gross_amount": str(gross_amount),
                "total_fees": str(total_fees),
                "total_fee_tax": str(total_fee_tax),
                "total_refunds": str(total_refunds_amount),
                "total_adjustments": str(total_adjustments),
                "net_amount": str(net_amount),
                "currency": "INR",
                "utr": utr,
                "status": "SETTLED",
                "payment_count": len(batch),
            }
            settlements.append(settlement)
            
            # Create settlement-payment mapping records
            for p in batch:
                sp = {
                    "settlement_id": settlement_id,
                    "payment_id": p["payment_id"],
                    "allocated_amount": p["amount"],
                }
                settlement_payments.append(sp)
    
    # Write settlements
    os.makedirs(output_dir, exist_ok=True)
    
    stl_path = os.path.join(output_dir, "settlements.jsonl")
    with open(stl_path, "w", encoding="utf-8") as f:
        for s in settlements:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    
    sp_path = os.path.join(output_dir, "settlement_payments.jsonl")
    with open(sp_path, "w", encoding="utf-8") as f:
        for sp in settlement_payments:
            f.write(json.dumps(sp, ensure_ascii=False) + "\n")
    
    print(f"✓ Generated {len(settlements)} settlements → {stl_path}")
    print(f"✓ Generated {len(settlement_payments)} settlement-payment links → {sp_path}")
    return settlements, settlement_payments


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_dir = os.path.join(base_dir, "data", "raw", "synthetic")
    
    with open(os.path.join(data_dir, "payments.jsonl")) as f:
        payments = [json.loads(line) for line in f]
    with open(os.path.join(data_dir, "fees.jsonl")) as f:
        fees = [json.loads(line) for line in f]
    with open(os.path.join(data_dir, "refunds.jsonl")) as f:
        refunds = [json.loads(line) for line in f]
    
    generate_settlements(payments, fees, refunds, data_dir)
