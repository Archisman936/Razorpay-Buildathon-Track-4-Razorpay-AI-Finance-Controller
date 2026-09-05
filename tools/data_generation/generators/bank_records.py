"""
Bank Record Generator — Step 17

Generates bank records FROM settlements + unrelated transactions.
Settlement-derived bank credits + noise (rent, salary, supplier payments).

Output: data/raw/synthetic/bank_records.jsonl
"""

import json
import os
import random
from decimal import Decimal
from datetime import datetime, timedelta

from .financial_rules import round_inr

random.seed(42)

# ── Configuration ────────────────────────────────────────────────────────────

# Non-settlement transaction types (noise)
NOISE_TRANSACTION_TYPES = [
    {"type": "SUPPLIER_PAYMENT", "desc_templates": [
        "NEFT TO SUPPLIER {ref}",
        "VENDOR PAYMENT {ref}",
        "IMPS SUPPLIER PAYMENT {ref}",
    ], "amount_range": (5000, 500000), "direction": "DEBIT"},
    
    {"type": "RENT", "desc_templates": [
        "RENT PAYMENT {ref}",
        "OFFICE RENT {ref}",
        "NEFT RENT {ref}",
    ], "amount_range": (25000, 200000), "direction": "DEBIT"},
    
    {"type": "SALARY", "desc_templates": [
        "SALARY {ref}",
        "NEFT SALARY TRANSFER {ref}",
        "PAYROLL {ref}",
    ], "amount_range": (15000, 150000), "direction": "DEBIT"},
    
    {"type": "UTILITIES", "desc_templates": [
        "ELECTRICITY BILL {ref}",
        "INTERNET CHARGES {ref}",
        "PHONE BILL {ref}",
        "WATER CHARGES {ref}",
    ], "amount_range": (500, 25000), "direction": "DEBIT"},
    
    {"type": "OTHER_TRANSFER", "desc_templates": [
        "FUND TRANSFER {ref}",
        "INTERNAL TRANSFER {ref}",
        "NEFT {ref}",
        "IMPS {ref}",
    ], "amount_range": (1000, 100000), "direction": "DEBIT"},
    
    {"type": "INTEREST_CREDIT", "desc_templates": [
        "INTEREST CREDIT {ref}",
        "INT CR {ref}",
    ], "amount_range": (100, 5000), "direction": "CREDIT"},
]

# How many noise transactions per merchant
NOISE_PER_MERCHANT = (50, 100)


def generate_bank_records(settlements: list, merchants: list,
                          output_dir: str) -> list:
    """
    Generate bank records from settlements and add noise transactions.
    
    Args:
        settlements: List of settlement dicts
        merchants: List of merchant dicts
        output_dir: Directory to write bank_records.jsonl
    
    Returns:
        List of bank record dicts
    """
    merchant_map = {m["merchant_id"]: m for m in merchants}
    
    bank_records = []
    record_idx = 0
    
    # Track running balances per merchant
    balances = {m["merchant_id"]: Decimal(str(random.randint(500000, 5000000))) 
                for m in merchants}
    
    # ── Settlement-derived bank credits ──────────────────────────────────
    
    for settlement in settlements:
        record_idx += 1
        merchant = merchant_map[settlement["merchant_id"]]
        
        # Bank credit date = settlement date or +1 day
        stl_dt = datetime.fromisoformat(
            settlement["settlement_date"].replace("+05:30", "")
        )
        bank_dt = stl_dt + timedelta(days=random.choice([0, 1]))
        value_dt = bank_dt + timedelta(days=random.choice([0, 1]))
        
        amount = Decimal(str(settlement["net_amount"]))
        balances[settlement["merchant_id"]] += amount
        
        record = {
            "bank_record_id": f"BNK_{record_idx:06d}",
            "merchant_id": settlement["merchant_id"],
            "account_id": merchant["bank_account_id"],
            "account_number": merchant["bank_account_number"],
            "bank_name": merchant["bank_name"],
            "transaction_date": bank_dt.strftime("%Y-%m-%d"),
            "value_date": value_dt.strftime("%Y-%m-%d"),
            "amount": str(amount),
            "currency": "INR",
            "transaction_type": "CREDIT",
            "reference": settlement["utr"],
            "description": f"RAZORPAY SETTLEMENT {settlement['settlement_id']}",
            "settlement_id": settlement["settlement_id"],
            "balance_after": str(round_inr(balances[settlement["merchant_id"]])),
            "category": "SETTLEMENT",
        }
        bank_records.append(record)
    
    # ── Noise transactions ───────────────────────────────────────────────
    
    for merchant in merchants:
        mid = merchant["merchant_id"]
        num_noise = random.randint(*NOISE_PER_MERCHANT)
        
        for _ in range(num_noise):
            record_idx += 1
            noise_type = random.choice(NOISE_TRANSACTION_TYPES)
            
            amount = round_inr(Decimal(str(
                random.randint(noise_type["amount_range"][0],
                              noise_type["amount_range"][1])
            )))
            
            if noise_type["direction"] == "DEBIT":
                balances[mid] -= amount
            else:
                balances[mid] += amount
            
            # Random date in August 2026
            bank_dt = datetime(2026, 8, 1) + timedelta(
                days=random.randint(0, 30),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            
            ref = f"REF{random.randint(100000, 999999)}"
            desc = random.choice(noise_type["desc_templates"]).format(ref=ref)
            
            record = {
                "bank_record_id": f"BNK_{record_idx:06d}",
                "merchant_id": mid,
                "account_id": merchant["bank_account_id"],
                "account_number": merchant["bank_account_number"],
                "bank_name": merchant["bank_name"],
                "transaction_date": bank_dt.strftime("%Y-%m-%d"),
                "value_date": bank_dt.strftime("%Y-%m-%d"),
                "amount": str(amount),
                "currency": "INR",
                "transaction_type": noise_type["direction"],
                "reference": ref,
                "description": desc,
                "settlement_id": None,
                "balance_after": str(round_inr(balances[mid])),
                "category": noise_type["type"],
            }
            bank_records.append(record)
    
    # Sort by date
    bank_records.sort(key=lambda r: r["transaction_date"])
    
    # Write to JSONL
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "bank_records.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for br in bank_records:
            f.write(json.dumps(br, ensure_ascii=False) + "\n")
    
    print(f"✓ Generated {len(bank_records)} bank records → {output_path}")
    return bank_records


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_dir = os.path.join(base_dir, "data", "raw", "synthetic")
    
    with open(os.path.join(data_dir, "settlements.jsonl")) as f:
        settlements = [json.loads(line) for line in f]
    with open(os.path.join(data_dir, "merchants.jsonl")) as f:
        merchants = [json.loads(line) for line in f]
    
    generate_bank_records(settlements, merchants, data_dir)
