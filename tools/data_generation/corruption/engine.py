"""
Corruption Engine — Steps 23-31

Main orchestrator that takes clean data and applies configured noise.

CLEAN DATA → CORRUPTION ENGINE → NOISY SOURCE DATA
"""

import json
import os
import copy
import random
import yaml

from .id_noise import apply_id_noise
from .description_noise import apply_description_noise
from .date_noise import apply_date_noise
from .amount_noise import apply_amount_noise
from .missing_records import remove_records
from .duplicates import add_duplicates
from .wrong_references import swap_references


def load_corruption_config(config_path: str) -> dict:
    """Load corruption configuration from YAML."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)["corruption"]


def load_jsonl(filepath: str) -> list:
    """Load JSONL file."""
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_jsonl(records: list, filepath: str):
    """Write records to JSONL file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def run_corruption(clean_dir: str, noisy_dir: str, config_path: str,
                   corruption_log_path: str) -> dict:
    """
    Run the full corruption pipeline.
    
    Args:
        clean_dir: Directory with clean JSONL files
        noisy_dir: Directory to write noisy JSONL files
        config_path: Path to corruption_config.yaml
        corruption_log_path: Path to write corruption log
    
    Returns:
        Summary statistics
    """
    config = load_corruption_config(config_path)
    seed = config.get("seed", 42)
    rng = random.Random(seed)
    
    os.makedirs(noisy_dir, exist_ok=True)
    
    all_corruption_logs = []
    stats = {}
    
    # ── Load all clean data (deep copies to avoid mutation) ──────────────
    
    print("\n📦 Loading clean data for corruption...")
    
    entity_files = {
        "merchants": ("merchants.jsonl", "merchant_id"),
        "customers": ("customers.jsonl", "customer_id"),
        "orders": ("orders.jsonl", "order_id"),
        "invoices": ("invoices.jsonl", "invoice_id"),
        "payments": ("payments.jsonl", "payment_id"),
        "fees": ("fees.jsonl", "fee_id"),
        "refunds": ("refunds.jsonl", "refund_id"),
        "settlements": ("settlements.jsonl", "settlement_id"),
        "settlement_payments": ("settlement_payments.jsonl", None),
        "bank_records": ("bank_records.jsonl", "bank_record_id"),
        "books": ("books.jsonl", "entry_id"),
        "gst_records": ("gst_records.jsonl", "gst_record_id"),
        "adjustments": ("adjustments.jsonl", "adjustment_id"),
    }
    
    data = {}
    for entity, (filename, _) in entity_files.items():
        filepath = os.path.join(clean_dir, filename)
        if os.path.exists(filepath):
            data[entity] = copy.deepcopy(load_jsonl(filepath))
            print(f"  Loaded {len(data[entity])} {entity}")
        else:
            data[entity] = []
            print(f"  ⚠ Missing {filename}")
    
    # ── Apply ID Noise ───────────────────────────────────────────────────
    
    if config.get("id_noise", {}).get("enabled"):
        print("\n🔀 Applying ID noise...")
        id_rate = config["id_noise"]["rate"]
        
        for entity in ["orders", "invoices", "payments", "settlements"]:
            _, id_field = entity_files[entity]
            if data[entity] and id_field:
                data[entity], log = apply_id_noise(
                    data[entity], id_field, id_rate, rng
                )
                all_corruption_logs.extend(log)
                print(f"  → {entity}: {len(log)} IDs corrupted")
    
    # ── Apply Description Noise ──────────────────────────────────────────
    
    if config.get("description_noise", {}).get("enabled"):
        print("\n📝 Applying description noise...")
        desc_rate = config["description_noise"]["rate"]
        
        if data["bank_records"]:
            data["bank_records"], log = apply_description_noise(
                data["bank_records"], "description", "settlement_id",
                desc_rate, rng
            )
            all_corruption_logs.extend(log)
            print(f"  → bank_records: {len(log)} descriptions corrupted")
    
    # ── Apply Date Noise ─────────────────────────────────────────────────
    
    if config.get("date_noise", {}).get("enabled"):
        print("\n📅 Applying date noise...")
        date_rate = config["date_noise"]["rate"]
        min_shift = config["date_noise"].get("min_shift_days", 1)
        max_shift = config["date_noise"].get("max_shift_days", 3)
        direction = config["date_noise"].get("direction", "BOTH")
        
        date_fields_map = {
            "bank_records": ["transaction_date", "value_date"],
            "books": ["entry_date"],
            "settlements": ["settlement_date"],
            "invoices": ["invoice_date"],
        }
        
        for entity, fields in date_fields_map.items():
            if data[entity]:
                data[entity], log = apply_date_noise(
                    data[entity], fields, date_rate,
                    min_shift, max_shift, direction, rng
                )
                all_corruption_logs.extend(log)
                print(f"  → {entity}: {len(log)} dates shifted")
    
    # ── Apply Amount Noise ───────────────────────────────────────────────
    
    if config.get("amount_noise", {}).get("enabled"):
        print("\n💰 Applying amount noise...")
        amt_rate = config["amount_noise"]["rate"]
        
        amount_fields_map = {
            "bank_records": "amount",
            "settlements": "net_amount",
        }
        
        for entity, field in amount_fields_map.items():
            if data[entity]:
                data[entity], log = apply_amount_noise(
                    data[entity], field, amt_rate, rng
                )
                all_corruption_logs.extend(log)
                print(f"  → {entity}: {len(log)} amounts corrupted")
    
    # ── Apply Missing Records ────────────────────────────────────────────
    
    if config.get("missing_records", {}).get("enabled"):
        print("\n🗑️ Applying missing records...")
        rates = config["missing_records"]["rates"]
        
        for entity, rate in rates.items():
            _, id_field = entity_files.get(entity, (None, None))
            if data.get(entity) and id_field:
                original_count = len(data[entity])
                data[entity], log = remove_records(
                    data[entity], rate, id_field, rng
                )
                all_corruption_logs.extend(log)
                print(f"  → {entity}: {original_count} → {len(data[entity])} "
                      f"({len(log)} removed)")
    
    # ── Apply Duplicates ─────────────────────────────────────────────────
    
    if config.get("duplicates", {}).get("enabled"):
        print("\n📋 Applying duplicates...")
        dup_rate = config["duplicates"]["rate"]
        targets = config["duplicates"].get("targets", [])
        
        for entity in targets:
            _, id_field = entity_files.get(entity, (None, None))
            if data.get(entity) and id_field:
                original_count = len(data[entity])
                data[entity], log = add_duplicates(
                    data[entity], id_field, dup_rate, rng
                )
                all_corruption_logs.extend(log)
                print(f"  → {entity}: {original_count} → {len(data[entity])} "
                      f"({len(log)} duplicates added)")
    
    # ── Apply Wrong References ───────────────────────────────────────────
    
    if config.get("wrong_references", {}).get("enabled"):
        print("\n🔗 Applying wrong references...")
        ref_rate = config["wrong_references"]["rate"]
        targets = config["wrong_references"].get("targets", [])
        
        ref_fields = {
            "bank_records": "settlement_id",
            "books": "reference_id",
        }
        
        for entity in targets:
            ref_field = ref_fields.get(entity)
            if data.get(entity) and ref_field:
                data[entity], log = swap_references(
                    data[entity], ref_field, ref_rate, rng
                )
                all_corruption_logs.extend(log)
                print(f"  → {entity}: {len(log)} references swapped")
    
    # ── Write noisy data ─────────────────────────────────────────────────
    
    print("\n💾 Writing noisy data...")
    for entity, (filename, _) in entity_files.items():
        if data[entity]:
            output_path = os.path.join(noisy_dir, filename)
            write_jsonl(data[entity], output_path)
            stats[entity] = len(data[entity])
            print(f"  → {filename}: {len(data[entity])} records")
    
    # ── Write corruption log ─────────────────────────────────────────────
    
    os.makedirs(os.path.dirname(corruption_log_path), exist_ok=True)
    with open(corruption_log_path, "w", encoding="utf-8") as f:
        for log_entry in all_corruption_logs:
            f.write(json.dumps(log_entry) + "\n")
    
    print(f"\n📊 Total corruptions applied: {len(all_corruption_logs)}")
    print(f"📝 Corruption log: {corruption_log_path}")
    
    stats["total_corruptions"] = len(all_corruption_logs)
    return stats


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    clean_dir = os.path.join(base_dir, "data", "raw", "synthetic")
    noisy_dir = os.path.join(base_dir, "data", "raw", "noisy")
    config_path = os.path.join(base_dir, "generator", "config", "corruption_config.yaml")
    log_path = os.path.join(base_dir, "data", "raw", "noisy", "corruption_log.jsonl")
    
    run_corruption(clean_dir, noisy_dir, config_path, log_path)
