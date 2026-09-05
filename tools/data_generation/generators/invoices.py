"""
Invoice Generator — Step 11

Generates invoices FROM completed orders (not independently).
Each eligible order gets exactly one invoice.

Output: data/raw/synthetic/invoices.jsonl
"""

import json
import os
import random
from datetime import datetime, timedelta

random.seed(42)


def generate_invoices(orders: list, merchants: list, output_dir: str) -> list:
    """
    Generate invoice records derived from completed orders.
    
    Args:
        orders: List of order dicts
        merchants: List of merchant dicts
        output_dir: Directory to write invoices.jsonl
    
    Returns:
        List of invoice dicts
    """
    merchant_map = {m["merchant_id"]: m for m in merchants}
    
    # Only completed orders get invoices
    eligible_orders = [o for o in orders if o["status"] == "COMPLETED"]
    
    invoices = []
    
    for i, order in enumerate(eligible_orders, start=1):
        merchant = merchant_map[order["merchant_id"]]
        
        # Invoice date = order date or slightly after (0-1 days)
        order_dt = datetime.fromisoformat(order["order_date"].replace("+05:30", "+05:30"))
        invoice_dt = order_dt + timedelta(hours=random.randint(0, 24))
        
        # Generate invoice number (business-format, not internal ID)
        fiscal_year = "2026-27"
        invoice_number = f"INV/{fiscal_year}/{merchant['merchant_id'][-3:]}/{i:05d}"
        
        invoice = {
            "invoice_id": f"INV_{i:06d}",
            "order_id": order["order_id"],
            "merchant_id": order["merchant_id"],
            "customer_id": order["customer_id"],
            "invoice_number": invoice_number,
            "invoice_date": invoice_dt.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "due_date": (invoice_dt + timedelta(days=30)).strftime("%Y-%m-%d"),
            "subtotal": order["subtotal"],
            "discount": order["discount"],
            "taxable_amount": order["taxable_amount"],
            "cgst": order["cgst"],
            "sgst": order["sgst"],
            "igst": order["igst"],
            "total_tax": order["total_tax"],
            "total_amount": order["total_amount"],
            "currency": "INR",
            "seller_gstin": merchant["gstin"],
            "seller_state": order["seller_state"],
            "buyer_state": order["buyer_state"],
            "status": "ISSUED",
        }
        invoices.append(invoice)
    
    # Write to JSONL
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "invoices.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for inv in invoices:
            f.write(json.dumps(inv, ensure_ascii=False) + "\n")
    
    print(f"✓ Generated {len(invoices)} invoices → {output_path}")
    return invoices


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_dir = os.path.join(base_dir, "data", "raw", "synthetic")
    
    with open(os.path.join(data_dir, "merchants.jsonl")) as f:
        merchants = [json.loads(line) for line in f]
    with open(os.path.join(data_dir, "orders.jsonl")) as f:
        orders = [json.loads(line) for line in f]
    
    generate_invoices(orders, merchants, data_dir)
