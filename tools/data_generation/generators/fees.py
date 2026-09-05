"""
Fee Generator — Step 14

Generates fees FROM payments using configurable fee rules.
Different payment methods have different fee structures.

Output: data/raw/synthetic/fees.jsonl
"""

import json
import os
import random
from decimal import Decimal

from .financial_rules import calc_fee, load_fee_rules

random.seed(42)


def generate_fees(payments: list, output_dir: str) -> list:
    """
    Generate fee records from payments using fee_rules.yaml.
    
    Args:
        payments: List of payment dicts
        output_dir: Directory to write fees.jsonl
    
    Returns:
        List of fee dicts
    """
    rules = load_fee_rules()
    fee_types = rules["fee_types"]
    
    fees = []
    
    for i, payment in enumerate(payments, start=1):
        # Only captured payments have fees
        if payment["status"] != "CAPTURED":
            # Still create a zero-fee record for tracking
            fee = {
                "fee_id": f"FEE_{i:06d}",
                "payment_id": payment["payment_id"],
                "merchant_id": payment["merchant_id"],
                "fee_type": "PLATFORM_FEE",
                "fee_amount": "0.00",
                "tax_amount": "0.00",
                "total_fee": "0.00",
                "currency": "INR",
                "payment_method": payment["payment_method"],
            }
            fees.append(fee)
            continue
        
        payment_amount = Decimal(str(payment["amount"]))
        payment_method = payment["payment_method"]
        
        # Calculate fee using central rules
        fee_calc = calc_fee(payment_amount, payment_method)
        
        # Pick a fee type
        fee_type = random.choice(fee_types)
        
        fee = {
            "fee_id": f"FEE_{i:06d}",
            "payment_id": payment["payment_id"],
            "merchant_id": payment["merchant_id"],
            "fee_type": fee_type,
            "fee_amount": str(fee_calc["fee_amount"]),
            "tax_amount": str(fee_calc["tax_amount"]),
            "total_fee": str(fee_calc["total_fee"]),
            "currency": "INR",
            "payment_method": payment_method,
        }
        fees.append(fee)
    
    # Write to JSONL
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "fees.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for fee in fees:
            f.write(json.dumps(fee, ensure_ascii=False) + "\n")
    
    print(f"✓ Generated {len(fees)} fees → {output_path}")
    return fees


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_dir = os.path.join(base_dir, "data", "raw", "synthetic")
    
    with open(os.path.join(data_dir, "payments.jsonl")) as f:
        payments = [json.loads(line) for line in f]
    
    generate_fees(payments, data_dir)
