"""
Adjustment Generator — Step 19

Generates ~50 adjustments referencing actual settlements/events.
Types: settlement adjustments, rounding, chargebacks, reversals, manual.

Output: data/raw/synthetic/adjustments.jsonl
"""

import json
import os
import random
from decimal import Decimal
from datetime import datetime, timedelta

from .financial_rules import round_inr

random.seed(42)

# ── Configuration ────────────────────────────────────────────────────────────

TARGET_COUNT = 50

ADJUSTMENT_TYPES = [
    {"type": "SETTLEMENT_ADJUSTMENT", "weight": 0.30,
     "amount_range": (50, 5000), "direction_weights": {"CREDIT": 0.6, "DEBIT": 0.4}},
    {"type": "ROUNDING", "weight": 0.20,
     "amount_range": (1, 50), "direction_weights": {"CREDIT": 0.5, "DEBIT": 0.5}},
    {"type": "CHARGEBACK", "weight": 0.20,
     "amount_range": (500, 20000), "direction_weights": {"CREDIT": 0.0, "DEBIT": 1.0}},
    {"type": "REVERSAL", "weight": 0.15,
     "amount_range": (100, 10000), "direction_weights": {"CREDIT": 0.5, "DEBIT": 0.5}},
    {"type": "MANUAL_ADJUSTMENT", "weight": 0.15,
     "amount_range": (10, 3000), "direction_weights": {"CREDIT": 0.7, "DEBIT": 0.3}},
]

REASONS = {
    "SETTLEMENT_ADJUSTMENT": [
        "Fee correction for previous cycle",
        "Settlement shortfall adjustment",
        "Rate revision adjustment",
        "Volume discount credit",
    ],
    "ROUNDING": [
        "Rounding difference",
        "Penny reconciliation",
        "Decimal truncation correction",
    ],
    "CHARGEBACK": [
        "Customer dispute - unauthorized transaction",
        "Customer dispute - product not received",
        "Chargeback from card network",
        "Fraud-related chargeback",
    ],
    "REVERSAL": [
        "Duplicate fee reversal",
        "Incorrect deduction reversal",
        "Previous adjustment reversal",
    ],
    "MANUAL_ADJUSTMENT": [
        "Manual credit by operations team",
        "Goodwill credit",
        "SLA breach compensation",
        "Migration adjustment",
    ],
}


def generate_adjustments(settlements: list, output_dir: str) -> list:
    """
    Generate adjustment records referencing actual settlements.
    
    Args:
        settlements: List of settlement dicts
        output_dir: Directory to write adjustments.jsonl
    
    Returns:
        List of adjustment dicts
    """
    if not settlements:
        print("⚠ No settlements to reference for adjustments")
        return []
    
    adjustments = []
    
    for i in range(1, TARGET_COUNT + 1):
        # Pick adjustment type
        types = [t["type"] for t in ADJUSTMENT_TYPES]
        weights = [t["weight"] for t in ADJUSTMENT_TYPES]
        adj_type = random.choices(types, weights=weights, k=1)[0]
        
        type_config = next(t for t in ADJUSTMENT_TYPES if t["type"] == adj_type)
        
        # Pick amount
        amount = round_inr(Decimal(str(
            random.randint(type_config["amount_range"][0],
                          type_config["amount_range"][1])
        )))
        
        # Pick direction
        directions = list(type_config["direction_weights"].keys())
        dir_weights = list(type_config["direction_weights"].values())
        direction = random.choices(directions, weights=dir_weights, k=1)[0]
        
        # Make amount negative for debits
        signed_amount = amount if direction == "CREDIT" else -amount
        
        # Reference a real settlement
        settlement = random.choice(settlements)
        
        # Adjustment date = settlement date + 0-5 days
        stl_dt = datetime.fromisoformat(
            settlement["settlement_date"].replace("+05:30", "")
        )
        adj_dt = stl_dt + timedelta(days=random.randint(0, 5))
        
        reason = random.choice(REASONS[adj_type])
        
        adjustment = {
            "adjustment_id": f"ADJ_{i:06d}",
            "settlement_id": settlement["settlement_id"],
            "merchant_id": settlement["merchant_id"],
            "adjustment_type": adj_type,
            "amount": str(signed_amount),
            "direction": direction,
            "reason": reason,
            "adjustment_date": adj_dt.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "currency": "INR",
            "status": "APPLIED",
        }
        adjustments.append(adjustment)
    
    # Write to JSONL
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "adjustments.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for a in adjustments:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    
    print(f"✓ Generated {len(adjustments)} adjustments → {output_path}")
    return adjustments


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_dir = os.path.join(base_dir, "data", "raw", "synthetic")
    
    with open(os.path.join(data_dir, "settlements.jsonl")) as f:
        settlements = [json.loads(line) for line in f]
    
    generate_adjustments(settlements, data_dir)
