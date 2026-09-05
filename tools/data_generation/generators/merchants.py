"""
Merchant Generator — Step 8

Generates 5 Indian e-commerce merchants with realistic attributes.
Output: data/raw/synthetic/merchants.jsonl
"""

import json
import os
import random

# Seed for reproducibility
random.seed(42)

# ── Merchant Templates ───────────────────────────────────────────────────────

MERCHANT_TEMPLATES = [
    {
        "merchant_name": "ShopEase India Pvt Ltd",
        "industry": "ELECTRONICS",
        "state": "Maharashtra",
        "city": "Mumbai",
        "gstin": "27AABCS1234E1Z5",
        "bank_account_number": "918020043210001",
        "bank_ifsc": "UTIB0000001",
        "bank_name": "Axis Bank",
    },
    {
        "merchant_name": "FashionBazaar Online",
        "industry": "FASHION",
        "state": "Karnataka",
        "city": "Bangalore",
        "gstin": "29AADCF5678G2Z3",
        "bank_account_number": "1234567890123456",
        "bank_ifsc": "HDFC0000002",
        "bank_name": "HDFC Bank",
    },
    {
        "merchant_name": "GroceryMart Express",
        "industry": "GROCERY",
        "state": "Delhi",
        "city": "New Delhi",
        "gstin": "07AAECG9012H3Z1",
        "bank_account_number": "50200045678901",
        "bank_ifsc": "ICIC0000003",
        "bank_name": "ICICI Bank",
    },
    {
        "merchant_name": "BookWorld Digital",
        "industry": "BOOKS_AND_MEDIA",
        "state": "Tamil Nadu",
        "city": "Chennai",
        "gstin": "33AAPCB3456I4Z9",
        "bank_account_number": "38765432109876",
        "bank_ifsc": "SBIN0000004",
        "bank_name": "State Bank of India",
    },
    {
        "merchant_name": "HomeDecor Hub",
        "industry": "HOME_AND_FURNITURE",
        "state": "Gujarat",
        "city": "Ahmedabad",
        "gstin": "24AAHCH7890J5Z7",
        "bank_account_number": "6543210987654321",
        "bank_ifsc": "KKBK0000005",
        "bank_name": "Kotak Mahindra Bank",
    },
]


def generate_merchants(output_dir: str) -> list:
    """
    Generate merchant records.
    
    Args:
        output_dir: Directory to write merchants.jsonl
    
    Returns:
        List of merchant dicts
    """
    merchants = []
    
    for i, template in enumerate(MERCHANT_TEMPLATES, start=1):
        merchant = {
            "merchant_id": f"MER_{i:06d}",
            "merchant_name": template["merchant_name"],
            "industry": template["industry"],
            "gstin": template["gstin"],
            "state": template["state"],
            "city": template["city"],
            "bank_account_id": f"ACC_{i:06d}",
            "bank_account_number": template["bank_account_number"],
            "bank_ifsc": template["bank_ifsc"],
            "bank_name": template["bank_name"],
            "currency": "INR",
            "timezone": "Asia/Kolkata",
            "status": "ACTIVE",
        }
        merchants.append(merchant)
    
    # Write to JSONL
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "merchants.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for m in merchants:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    
    print(f"✓ Generated {len(merchants)} merchants → {output_path}")
    return merchants


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    output_dir = os.path.join(base_dir, "data", "raw", "synthetic")
    generate_merchants(output_dir)
