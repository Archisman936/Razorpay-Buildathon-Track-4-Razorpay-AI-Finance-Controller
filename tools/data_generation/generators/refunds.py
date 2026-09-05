"""
Refund Generator — Step 15

Generates refunds FROM a subset of successful payments.
Supports FULL, PARTIAL, and REVERSAL refund types.

Output: data/raw/synthetic/refunds.jsonl
"""

import json
import os
import random
from decimal import Decimal
from datetime import datetime, timedelta

from .financial_rules import calc_refund_amount, round_inr

random.seed(42)

# ── Configuration ────────────────────────────────────────────────────────────

REFUND_RATE = 0.09  # ~9% of captured payments get refunds → ~150 refunds from ~1700

REFUND_TYPE_WEIGHTS = {
    "FULL": 0.50,
    "PARTIAL": 0.35,
    "REVERSAL": 0.15,
}

REFUND_REASONS = [
    "Customer requested cancellation",
    "Product damaged during delivery",
    "Wrong item delivered",
    "Product not as described",
    "Duplicate payment",
    "Order not fulfilled",
    "Customer changed mind",
    "Size/color mismatch",
    "Late delivery",
    "Quality not satisfactory",
    "Fraudulent transaction",
    "Payment dispute",
]


def _pick_refund_type() -> str:
    """Pick refund type based on weights."""
    types = list(REFUND_TYPE_WEIGHTS.keys())
    weights = list(REFUND_TYPE_WEIGHTS.values())
    return random.choices(types, weights=weights, k=1)[0]


def generate_refunds(payments: list, orders: list, output_dir: str) -> list:
    """
    Generate refund records from a subset of captured payments.
    
    Args:
        payments: List of payment dicts
        orders: List of order dicts
        output_dir: Directory to write refunds.jsonl
    
    Returns:
        List of refund dicts
    """
    order_map = {o["order_id"]: o for o in orders}
    
    # Only captured payments can be refunded
    captured_payments = [p for p in payments if p["status"] == "CAPTURED"]
    
    # Select a subset for refunds
    num_refunds = int(len(captured_payments) * REFUND_RATE)
    refund_payments = random.sample(captured_payments, min(num_refunds, len(captured_payments)))
    
    refunds = []
    
    for i, payment in enumerate(refund_payments, start=1):
        refund_type = _pick_refund_type()
        payment_amount = Decimal(str(payment["amount"]))
        
        # Calculate refund amount
        if refund_type == "PARTIAL":
            partial_fraction = Decimal(str(round(random.uniform(0.10, 0.90), 2)))
            refund_amount = calc_refund_amount(payment_amount, refund_type, partial_fraction)
        else:
            refund_amount = calc_refund_amount(payment_amount, refund_type)
        
        # Refund date = payment date + 1-15 days
        payment_dt = datetime.fromisoformat(payment["payment_date"].replace("+05:30", ""))
        refund_dt = payment_dt + timedelta(days=random.randint(1, 15))
        
        refund = {
            "refund_id": f"REF_{i:06d}",
            "payment_id": payment["payment_id"],
            "order_id": payment["order_id"],
            "merchant_id": payment["merchant_id"],
            "refund_amount": str(refund_amount),
            "refund_type": refund_type,
            "reason": random.choice(REFUND_REASONS),
            "status": "PROCESSED",
            "refund_date": refund_dt.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "currency": "INR",
        }
        refunds.append(refund)
    
    # Write to JSONL
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "refunds.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for r in refunds:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    
    print(f"✓ Generated {len(refunds)} refunds → {output_path}")
    return refunds


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_dir = os.path.join(base_dir, "data", "raw", "synthetic")
    
    with open(os.path.join(data_dir, "payments.jsonl")) as f:
        payments = [json.loads(line) for line in f]
    with open(os.path.join(data_dir, "orders.jsonl")) as f:
        orders = [json.loads(line) for line in f]
    
    generate_refunds(payments, orders, data_dir)
