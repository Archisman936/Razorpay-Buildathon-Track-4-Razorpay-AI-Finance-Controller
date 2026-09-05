"""
GST Record Generator — Step 12

Generates GST records FROM invoices (not independently).
Each invoice gets exactly one GST record.

Output: data/raw/synthetic/gst_records.jsonl
"""

import json
import os
import random
from datetime import datetime

random.seed(42)

# Buyer GSTIN patterns by state code
STATE_CODES = {
    "Maharashtra": "27",
    "Karnataka": "29",
    "Delhi": "07",
    "Tamil Nadu": "33",
    "Gujarat": "24",
    "Uttar Pradesh": "09",
    "Rajasthan": "08",
    "West Bengal": "19",
    "Telangana": "36",
    "Kerala": "32",
}


def _generate_buyer_gstin(state: str, index: int) -> str:
    """Generate a plausible buyer GSTIN for a given state."""
    state_code = STATE_CODES.get(state, "99")
    # Format: {state_code}{10 alphanumeric}{1 check}
    middle = f"ABCDE{index:04d}F"
    return f"{state_code}{middle}1Z{random.randint(1,9)}"


def generate_gst_records(invoices: list, merchants: list,
                         output_dir: str) -> list:
    """
    Generate GST records derived from invoices.
    
    Args:
        invoices: List of invoice dicts
        merchants: List of merchant dicts
        output_dir: Directory to write gst_records.jsonl
    
    Returns:
        List of GST record dicts
    """
    merchant_map = {m["merchant_id"]: m for m in merchants}
    
    gst_records = []
    
    for i, invoice in enumerate(invoices, start=1):
        merchant = merchant_map[invoice["merchant_id"]]
        
        # Determine filing period from invoice date
        inv_date = datetime.fromisoformat(
            invoice["invoice_date"].replace("+05:30", "+05:30")
        )
        filing_period = inv_date.strftime("%m-%Y")  # e.g., "08-2026"
        
        # Determine supply type
        if invoice["seller_state"] == invoice["buyer_state"]:
            supply_type = "INTRA_STATE"
        else:
            supply_type = "INTER_STATE"
        
        # Generate buyer GSTIN (B2B assumption for some, B2C for others)
        has_buyer_gstin = random.random() < 0.60  # 60% B2B
        buyer_gstin = _generate_buyer_gstin(invoice["buyer_state"], i) if has_buyer_gstin else None
        
        gst_record = {
            "gst_record_id": f"GST_{i:06d}",
            "invoice_id": invoice["invoice_id"],
            "invoice_number": invoice["invoice_number"],
            "merchant_id": invoice["merchant_id"],
            "seller_gstin": merchant["gstin"],
            "buyer_gstin": buyer_gstin,
            "supply_type": supply_type,
            "taxable_amount": invoice["taxable_amount"],
            "cgst": invoice["cgst"],
            "sgst": invoice["sgst"],
            "igst": invoice["igst"],
            "total_tax": invoice["total_tax"],
            "total_amount": invoice["total_amount"],
            "filing_period": filing_period,
            "return_type": "GSTR-1",
            "status": "FILED",
        }
        gst_records.append(gst_record)
    
    # Write to JSONL
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "gst_records.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for g in gst_records:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")
    
    print(f"✓ Generated {len(gst_records)} GST records → {output_path}")
    return gst_records


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_dir = os.path.join(base_dir, "data", "raw", "synthetic")
    
    with open(os.path.join(data_dir, "merchants.jsonl")) as f:
        merchants = [json.loads(line) for line in f]
    with open(os.path.join(data_dir, "invoices.jsonl")) as f:
        invoices = [json.loads(line) for line in f]
    
    generate_gst_records(invoices, merchants, data_dir)
