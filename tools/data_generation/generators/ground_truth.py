"""
Ground Truth Generator — Step 21

Creates authoritative truth labels for evaluation:
- event_links.jsonl: All entity relationships
- reconciliation_truth.jsonl: Expected reconciliation matches
- exception_truth.jsonl: Expected exceptions/mismatches

Output: data/ground_truth/
"""

import json
import os
from collections import defaultdict


def generate_ground_truth(orders: list, invoices: list, payments: list,
                          fees: list, refunds: list, settlements: list,
                          settlement_payments: list, bank_records: list,
                          books: list, gst_records: list, adjustments: list,
                          output_dir: str) -> dict:
    """
    Generate ground truth files from clean data.
    
    Returns dict with lists: event_links, reconciliation_truth, exception_truth
    """
    os.makedirs(output_dir, exist_ok=True)
    
    event_links = []
    reconciliation_truth = []
    exception_truth = []
    
    # Build lookups
    order_map = {o["order_id"]: o for o in orders}
    payment_map = {p["payment_id"]: p for p in payments}
    settlement_map = {s["settlement_id"]: s for s in settlements}
    
    # ── 1. Order → Invoice links ─────────────────────────────────────────
    
    invoice_orders = set()
    for inv in invoices:
        event_links.append({
            "source_type": "invoice",
            "source_id": inv["invoice_id"],
            "target_type": "order",
            "target_id": inv["order_id"],
            "relationship": "DERIVED_FROM",
            "expected_status": "MATCH",
        })
        invoice_orders.add(inv["order_id"])
        
        reconciliation_truth.append({
            "pair_type": "ORDER_INVOICE",
            "source_type": "order",
            "source_id": inv["order_id"],
            "target_type": "invoice",
            "target_id": inv["invoice_id"],
            "expected_result": "MATCH",
            "match_fields": ["total_amount", "taxable_amount", "total_tax"],
        })
    
    # Orders without invoices → exceptions
    for order in orders:
        if order["status"] == "COMPLETED" and order["order_id"] not in invoice_orders:
            exception_truth.append({
                "entity_type": "order",
                "entity_id": order["order_id"],
                "exception_type": "MISSING_INVOICE",
                "description": f"Completed order {order['order_id']} has no invoice",
            })
    
    # ── 2. Order → Payment links ─────────────────────────────────────────
    
    for payment in payments:
        event_links.append({
            "source_type": "payment",
            "source_id": payment["payment_id"],
            "target_type": "order",
            "target_id": payment["order_id"],
            "relationship": "PAYS_FOR",
            "expected_status": "MATCH",
        })
        
        if payment["status"] == "CAPTURED":
            reconciliation_truth.append({
                "pair_type": "ORDER_PAYMENT",
                "source_type": "order",
                "source_id": payment["order_id"],
                "target_type": "payment",
                "target_id": payment["payment_id"],
                "expected_result": "MATCH",
                "match_fields": ["total_amount"],
            })
    
    # ── 3. Payment → Fee links ───────────────────────────────────────────
    
    for fee in fees:
        event_links.append({
            "source_type": "fee",
            "source_id": fee["fee_id"],
            "target_type": "payment",
            "target_id": fee["payment_id"],
            "relationship": "CHARGED_ON",
            "expected_status": "MATCH",
        })
    
    # ── 4. Payment → Refund links ────────────────────────────────────────
    
    for refund in refunds:
        event_links.append({
            "source_type": "refund",
            "source_id": refund["refund_id"],
            "target_type": "payment",
            "target_id": refund["payment_id"],
            "relationship": "REFUNDS",
            "expected_status": "MATCH",
        })
    
    # ── 5. Settlement → Payment links ────────────────────────────────────
    
    for sp in settlement_payments:
        event_links.append({
            "source_type": "settlement",
            "source_id": sp["settlement_id"],
            "target_type": "payment",
            "target_id": sp["payment_id"],
            "relationship": "SETTLES",
            "expected_status": "MATCH",
        })
    
    # ── 6. Settlement → Bank Record links ────────────────────────────────
    
    for bank in bank_records:
        if bank.get("settlement_id"):
            event_links.append({
                "source_type": "bank_record",
                "source_id": bank["bank_record_id"],
                "target_type": "settlement",
                "target_id": bank["settlement_id"],
                "relationship": "CORRESPONDS_TO",
                "expected_status": "MATCH",
            })
            
            reconciliation_truth.append({
                "pair_type": "SETTLEMENT_BANK",
                "source_type": "settlement",
                "source_id": bank["settlement_id"],
                "target_type": "bank_record",
                "target_id": bank["bank_record_id"],
                "expected_result": "MATCH",
                "match_fields": ["net_amount"],
            })
    
    # ── 7. Invoice → GST Record links ───────────────────────────────────
    
    for gst in gst_records:
        event_links.append({
            "source_type": "gst_record",
            "source_id": gst["gst_record_id"],
            "target_type": "invoice",
            "target_id": gst["invoice_id"],
            "relationship": "TAX_FOR",
            "expected_status": "MATCH",
        })
        
        reconciliation_truth.append({
            "pair_type": "INVOICE_GST",
            "source_type": "invoice",
            "source_id": gst["invoice_id"],
            "target_type": "gst_record",
            "target_id": gst["gst_record_id"],
            "expected_result": "MATCH",
            "match_fields": ["taxable_amount", "total_tax", "cgst", "sgst", "igst"],
        })
    
    # ── 8. Book entry links ──────────────────────────────────────────────
    
    for entry in books:
        event_links.append({
            "source_type": "book_entry",
            "source_id": entry["entry_id"],
            "target_type": entry["reference_type"].lower(),
            "target_id": entry["reference_id"],
            "relationship": "RECORDS",
            "expected_status": "MATCH",
        })
    
    # ── 9. Adjustment links ──────────────────────────────────────────────
    
    for adj in adjustments:
        event_links.append({
            "source_type": "adjustment",
            "source_id": adj["adjustment_id"],
            "target_type": "settlement",
            "target_id": adj["settlement_id"],
            "relationship": "ADJUSTS",
            "expected_status": "MATCH",
        })
    
    # ── Write output files ───────────────────────────────────────────────
    
    links_path = os.path.join(output_dir, "event_links.jsonl")
    with open(links_path, "w", encoding="utf-8") as f:
        for link in event_links:
            f.write(json.dumps(link) + "\n")
    
    recon_path = os.path.join(output_dir, "reconciliation_truth.jsonl")
    with open(recon_path, "w", encoding="utf-8") as f:
        for rt in reconciliation_truth:
            f.write(json.dumps(rt) + "\n")
    
    exc_path = os.path.join(output_dir, "exception_truth.jsonl")
    with open(exc_path, "w", encoding="utf-8") as f:
        for et in exception_truth:
            f.write(json.dumps(et) + "\n")
    
    print(f"✓ Generated {len(event_links)} event links → {links_path}")
    print(f"✓ Generated {len(reconciliation_truth)} reconciliation truths → {recon_path}")
    print(f"✓ Generated {len(exception_truth)} exception truths → {exc_path}")
    
    return {
        "event_links": event_links,
        "reconciliation_truth": reconciliation_truth,
        "exception_truth": exception_truth,
    }
