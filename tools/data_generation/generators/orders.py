"""
Order Generator — Step 10

Generates 2,000 orders as the starting point of the transactional world.
Each order contains proper subtotal/discount/tax/total calculations.
~85% completed, ~10% cancelled, ~5% pending.

Output: data/raw/synthetic/orders.jsonl
"""

import json
import os
import random
from datetime import datetime, timedelta
from decimal import Decimal

from .financial_rules import calc_order_amounts, round_inr

random.seed(42)

# ── Configuration ────────────────────────────────────────────────────────────

# Order date range: August 2026
START_DATE = datetime(2026, 8, 1)
END_DATE = datetime(2026, 8, 31)

# Status distribution
STATUS_WEIGHTS = {
    "COMPLETED": 0.85,
    "CANCELLED": 0.10,
    "PENDING": 0.05,
}

# Price ranges by industry
PRICE_RANGES = {
    "ELECTRONICS": (500, 50000),
    "FASHION": (200, 15000),
    "GROCERY": (100, 5000),
    "BOOKS_AND_MEDIA": (50, 3000),
    "HOME_AND_FURNITURE": (500, 30000),
}

# Discount rates (probability, rate)
DISCOUNT_OPTIONS = [
    (0.40, Decimal("0.00")),    # 40% no discount
    (0.20, Decimal("0.05")),    # 20% get 5% off
    (0.15, Decimal("0.10")),    # 15% get 10% off
    (0.10, Decimal("0.15")),    # 10% get 15% off
    (0.08, Decimal("0.20")),    # 8% get 20% off
    (0.05, Decimal("0.25")),    # 5% get 25% off
    (0.02, Decimal("0.30")),    # 2% get 30% off
]

# Item count distribution
ITEM_COUNTS = [1, 1, 1, 1, 2, 2, 2, 3, 3, 4, 5]


def _pick_status() -> str:
    """Pick order status based on weights."""
    r = random.random()
    cumulative = 0
    for status, weight in STATUS_WEIGHTS.items():
        cumulative += weight
        if r <= cumulative:
            return status
    return "COMPLETED"


def _pick_discount_rate() -> Decimal:
    """Pick a discount rate based on probability distribution."""
    r = random.random()
    cumulative = 0
    for prob, rate in DISCOUNT_OPTIONS:
        cumulative += prob
        if r <= cumulative:
            return rate
    return Decimal("0.00")


def _random_date() -> str:
    """Generate a random date in August 2026."""
    delta = (END_DATE - START_DATE).days
    random_day = START_DATE + timedelta(days=random.randint(0, delta))
    # Add random time
    random_hour = random.randint(0, 23)
    random_minute = random.randint(0, 59)
    random_second = random.randint(0, 59)
    dt = random_day.replace(hour=random_hour, minute=random_minute, second=random_second)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+05:30")


def generate_orders(merchants: list, customers: list, output_dir: str,
                    count: int = 2000) -> list:
    """
    Generate order records.
    
    Args:
        merchants: List of merchant dicts
        customers: List of customer dicts  
        output_dir: Directory to write orders.jsonl
        count: Number of orders to generate
    
    Returns:
        List of order dicts
    """
    # Build merchant lookup
    merchant_map = {m["merchant_id"]: m for m in merchants}
    
    # Group customers by merchant
    customers_by_merchant = {}
    for c in customers:
        mid = c["merchant_id"]
        if mid not in customers_by_merchant:
            customers_by_merchant[mid] = []
        customers_by_merchant[mid].append(c)
    
    orders = []
    
    for i in range(1, count + 1):
        # Pick a random merchant
        merchant = random.choice(merchants)
        merchant_id = merchant["merchant_id"]
        
        # Pick a customer for this merchant
        merchant_customers = customers_by_merchant.get(merchant_id, [])
        if not merchant_customers:
            # Fallback: pick any customer
            customer = random.choice(customers)
        else:
            customer = random.choice(merchant_customers)
        
        # Calculate order amounts
        industry = merchant["industry"]
        price_range = PRICE_RANGES.get(industry, (100, 10000))
        
        num_items = random.choice(ITEM_COUNTS)
        subtotal = Decimal("0.00")
        for _ in range(num_items):
            item_price = Decimal(str(random.randint(price_range[0], price_range[1])))
            subtotal += item_price
        subtotal = round_inr(subtotal)
        
        discount_rate = _pick_discount_rate()
        
        # Determine if intra-state or inter-state
        seller_state = merchant["state"]
        buyer_state = customer["state"]
        
        amounts = calc_order_amounts(subtotal, discount_rate, seller_state, buyer_state)
        
        status = _pick_status()
        order_date = _random_date()
        
        order = {
            "order_id": f"ORD_{i:06d}",
            "merchant_id": merchant_id,
            "customer_id": customer["customer_id"],
            "order_date": order_date,
            "subtotal": str(subtotal),
            "discount_rate": str(discount_rate),
            "discount": str(amounts["discount"]),
            "taxable_amount": str(amounts["taxable_amount"]),
            "cgst": str(amounts["cgst"]),
            "sgst": str(amounts["sgst"]),
            "igst": str(amounts["igst"]),
            "total_tax": str(amounts["total_tax"]),
            "total_amount": str(amounts["total_amount"]),
            "currency": "INR",
            "status": status,
            "seller_state": seller_state,
            "buyer_state": buyer_state,
        }
        orders.append(order)
    
    # Write to JSONL
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "orders.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for o in orders:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    
    print(f"✓ Generated {len(orders)} orders → {output_path}")
    return orders


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_dir = os.path.join(base_dir, "data", "raw", "synthetic")
    
    # Load dependencies
    with open(os.path.join(data_dir, "merchants.jsonl")) as f:
        merchants = [json.loads(line) for line in f]
    with open(os.path.join(data_dir, "customers.jsonl")) as f:
        customers = [json.loads(line) for line in f]
    
    generate_orders(merchants, customers, data_dir)
