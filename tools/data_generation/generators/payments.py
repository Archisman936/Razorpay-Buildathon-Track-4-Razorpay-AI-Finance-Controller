"""
Payment Generator — Step 13

Generates payments FROM orders (not independently).
For normal successful payments: payment.amount = order.total_amount

Output: data/raw/synthetic/payments.jsonl
"""

import json
import os
import random
from datetime import datetime, timedelta

random.seed(42)

# ── Configuration ────────────────────────────────────────────────────────────

PAYMENT_METHODS = ["UPI", "CARD", "NETBANKING", "WALLET"]
PAYMENT_METHOD_WEIGHTS = [0.45, 0.30, 0.15, 0.10]

GATEWAYS = ["RAZORPAY", "RAZORPAY"]  # We use Razorpay as primary gateway

PAYMENT_STATUS_FOR_ORDER = {
    "COMPLETED": "CAPTURED",
    "CANCELLED": "FAILED",
    "PENDING": "PENDING",
}

# Card networks for CARD payments
CARD_NETWORKS = ["VISA", "MASTERCARD", "RUPAY", "AMEX"]
CARD_NETWORK_WEIGHTS = [0.35, 0.35, 0.25, 0.05]

# UPI apps
UPI_APPS = ["GPAY", "PHONEPE", "PAYTM", "BHIM", "CRED"]

# Wallet providers
WALLET_PROVIDERS = ["PAYTM", "MOBIKWIK", "FREECHARGE", "PHONEPE"]

# Bank names for NETBANKING
NETBANKING_BANKS = ["HDFC", "ICICI", "SBI", "AXIS", "KOTAK", "PNB", "BOB"]


def _pick_payment_method() -> str:
    """Pick payment method based on distribution."""
    return random.choices(PAYMENT_METHODS, weights=PAYMENT_METHOD_WEIGHTS, k=1)[0]


def _generate_gateway_reference() -> str:
    """Generate a Razorpay-style payment reference."""
    prefix = "pay"
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    ref = "".join(random.choices(chars, k=14))
    return f"{prefix}_{ref}"


def _generate_utr() -> str:
    """Generate a UTR (Unique Transaction Reference) number."""
    # UTR format varies: typically 12-22 digits
    bank_code = random.choice(["HDFC", "ICIC", "SBIN", "UTIB", "KKBK"])
    return f"{bank_code}{random.randint(10**12, 10**13 - 1)}"


def generate_payments(orders: list, output_dir: str) -> list:
    """
    Generate payment records from orders.
    
    Args:
        orders: List of order dicts
        output_dir: Directory to write payments.jsonl
    
    Returns:
        List of payment dicts
    """
    payments = []
    
    for i, order in enumerate(orders, start=1):
        # Payment date = order date + small delay (0-30 minutes)
        order_dt = datetime.fromisoformat(order["order_date"].replace("+05:30", ""))
        payment_dt = order_dt + timedelta(minutes=random.randint(0, 30))
        
        payment_method = _pick_payment_method()
        status = PAYMENT_STATUS_FOR_ORDER.get(order["status"], "PENDING")
        
        # Payment amount = order total (clean data, no discrepancies)
        amount = order["total_amount"]
        
        # Generate method-specific details
        method_details = {}
        if payment_method == "CARD":
            network = random.choices(CARD_NETWORKS, weights=CARD_NETWORK_WEIGHTS, k=1)[0]
            method_details = {
                "card_network": network,
                "card_last4": f"{random.randint(1000, 9999)}",
                "card_type": random.choice(["DEBIT", "CREDIT"]),
            }
        elif payment_method == "UPI":
            method_details = {
                "upi_app": random.choice(UPI_APPS),
                "upi_id": f"user{random.randint(1000,9999)}@{random.choice(['oksbi','okhdfcbank','ybl','paytm'])}",
            }
        elif payment_method == "WALLET":
            method_details = {
                "wallet_provider": random.choice(WALLET_PROVIDERS),
            }
        elif payment_method == "NETBANKING":
            method_details = {
                "bank_name": random.choice(NETBANKING_BANKS),
            }
        
        gateway_reference = _generate_gateway_reference()
        utr = _generate_utr() if status == "CAPTURED" else None
        
        payment = {
            "payment_id": f"PAY_{i:06d}",
            "order_id": order["order_id"],
            "merchant_id": order["merchant_id"],
            "customer_id": order["customer_id"],
            "amount": amount,
            "currency": "INR",
            "payment_method": payment_method,
            "status": status,
            "gateway": "RAZORPAY",
            "gateway_reference": gateway_reference,
            "utr": utr,
            "payment_date": payment_dt.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "captured_at": payment_dt.strftime("%Y-%m-%dT%H:%M:%S+05:30") if status == "CAPTURED" else None,
            **method_details,
        }
        payments.append(payment)
    
    # Write to JSONL
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "payments.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for p in payments:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    
    print(f"✓ Generated {len(payments)} payments → {output_path}")
    return payments


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_dir = os.path.join(base_dir, "data", "raw", "synthetic")
    
    with open(os.path.join(data_dir, "orders.jsonl")) as f:
        orders = [json.loads(line) for line in f]
    
    generate_payments(orders, data_dir)
