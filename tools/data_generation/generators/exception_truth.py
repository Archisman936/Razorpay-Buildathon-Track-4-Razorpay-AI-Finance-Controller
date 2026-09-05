"""
Exception Truth Generator

Maps corruption log entries → exception ground truth labels.
This runs AFTER corruption is applied to create labels for the
ambiguous multiclass classifier.

Corruption Cause → Exception Class mapping:
    ID_NOISE           → FORMAT_MISMATCH
    DESCRIPTION_NOISE  → DESCRIPTION_MISMATCH
    DATE_NOISE         → TIMING_DIFFERENCE
    AMOUNT_NOISE       → AMOUNT_DISCREPANCY (sub-classes: FEE_ADJUSTMENT, 
                          PARTIAL_SETTLEMENT, TAX_MISMATCH, ROUNDING, UNKNOWN)
    MISSING_RECORD     → MISSING_RECORD
    DUPLICATE          → DUPLICATE
    WRONG_REFERENCE    → WRONG_REFERENCE
"""

import json
import os

# ── Corruption type → Exception class mapping ───────────────────────────────

EXCEPTION_CLASS_MAP = {
    # Corruption type → (exception_class, severity, resolution_hint)
    "ID_NOISE": {
        "exception_class": "FORMAT_MISMATCH",
        "severity": "LOW",
        "resolution_hint": "Normalize ID formats and retry matching",
        "requires_manual_review": False,
    },
    "DESCRIPTION_NOISE": {
        "exception_class": "DESCRIPTION_MISMATCH",
        "severity": "LOW",
        "resolution_hint": "Apply fuzzy text matching on narration/description",
        "requires_manual_review": False,
    },
    "DATE_NOISE": {
        "exception_class": "TIMING_DIFFERENCE",
        "severity": "LOW",
        "resolution_hint": "Apply date tolerance window (T+1 to T+3)",
        "requires_manual_review": False,
    },
    "AMOUNT_NOISE": {
        "exception_class": "AMOUNT_DISCREPANCY",
        "severity": "MEDIUM",
        "resolution_hint": "Investigate fee/tax/settlement arithmetic",
        "requires_manual_review": True,
    },
    "MISSING_RECORD": {
        "exception_class": "MISSING_RECORD",
        "severity": "HIGH",
        "resolution_hint": "Unmatched record — no counterpart found in target system",
        "requires_manual_review": True,
    },
    "DUPLICATE": {
        "exception_class": "DUPLICATE",
        "severity": "MEDIUM",
        "resolution_hint": "Potential duplicate entry — verify and deduplicate",
        "requires_manual_review": True,
    },
    "WRONG_REFERENCE": {
        "exception_class": "WRONG_REFERENCE",
        "severity": "HIGH",
        "resolution_hint": "Cross-reference points to incorrect entity — manual investigation needed",
        "requires_manual_review": True,
    },
}

# Sub-classes for AMOUNT_NOISE based on cause field
AMOUNT_SUBCLASS_MAP = {
    "FEE_ADJUSTMENT": {
        "exception_subclass": "FEE_ADJUSTMENT",
        "severity": "MEDIUM",
        "resolution_hint": "Fee calculation difference — verify fee rules applied",
    },
    "PARTIAL_SETTLEMENT": {
        "exception_subclass": "PARTIAL_SETTLEMENT",
        "severity": "HIGH",
        "resolution_hint": "Settlement amount doesn't match expected — check partial payout",
    },
    "TAX_MISMATCH": {
        "exception_subclass": "TAX_MISMATCH",
        "severity": "MEDIUM",
        "resolution_hint": "Tax calculation discrepancy — verify GST rates",
    },
    "ROUNDING": {
        "exception_subclass": "ROUNDING",
        "severity": "LOW",
        "resolution_hint": "Minor rounding difference — auto-resolve within threshold",
    },
    "UNKNOWN": {
        "exception_subclass": "UNKNOWN",
        "severity": "HIGH",
        "resolution_hint": "Unexplained amount difference — escalate for manual review",
    },
}

# All possible exception classes for the classifier
ALL_EXCEPTION_CLASSES = [
    "FORMAT_MISMATCH",
    "DESCRIPTION_MISMATCH",
    "TIMING_DIFFERENCE",
    "AMOUNT_DISCREPANCY",
    "AMOUNT_DISCREPANCY__FEE_ADJUSTMENT",
    "AMOUNT_DISCREPANCY__PARTIAL_SETTLEMENT",
    "AMOUNT_DISCREPANCY__TAX_MISMATCH",
    "AMOUNT_DISCREPANCY__ROUNDING",
    "AMOUNT_DISCREPANCY__UNKNOWN",
    "MISSING_RECORD",
    "DUPLICATE",
    "WRONG_REFERENCE",
]


def generate_exception_truth(corruption_log_path: str, output_dir: str) -> list:
    """
    Generate exception ground truth from the corruption log.
    
    Each corruption log entry becomes an exception truth record with:
    - A unique case ID
    - The exception class label
    - The corruption details (original/corrupted values)
    - Severity and resolution hints
    
    Args:
        corruption_log_path: Path to corruption_log.jsonl
        output_dir: Directory to write exception_truth.jsonl
    
    Returns:
        List of exception truth records
    """
    # Load corruption log
    corruption_entries = []
    with open(corruption_log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                corruption_entries.append(json.loads(line))
    
    exceptions = []
    case_idx = 0
    
    for entry in corruption_entries:
        corruption_type = entry.get("type", "")
        mapping = EXCEPTION_CLASS_MAP.get(corruption_type)
        
        if not mapping:
            continue
        
        case_idx += 1
        
        # Base exception record
        exception = {
            "case_id": f"EXC_{case_idx:06d}",
            "exception_class": mapping["exception_class"],
            "exception_subclass": None,
            "severity": mapping["severity"],
            "resolution_hint": mapping["resolution_hint"],
            "requires_manual_review": mapping["requires_manual_review"],
            "corruption_type": corruption_type,
            "affected_entity_id": entry.get("record_id", ""),
            "affected_field": entry.get("field", ""),
            "original_value": entry.get("original", entry.get("original_id", "")),
            "corrupted_value": entry.get("corrupted", entry.get("duplicate_id", "")),
        }
        
        # For AMOUNT_NOISE, add sub-class based on cause
        if corruption_type == "AMOUNT_NOISE":
            cause = entry.get("cause", "UNKNOWN")
            subclass_info = AMOUNT_SUBCLASS_MAP.get(cause, AMOUNT_SUBCLASS_MAP["UNKNOWN"])
            exception["exception_subclass"] = subclass_info["exception_subclass"]
            exception["exception_class"] = f"AMOUNT_DISCREPANCY__{subclass_info['exception_subclass']}"
            exception["severity"] = subclass_info["severity"]
            exception["resolution_hint"] = subclass_info["resolution_hint"]
        
        # For MISSING_RECORD, set entity type
        if corruption_type == "MISSING_RECORD":
            exception["missing_entity_type"] = entry.get("entity_type", "")
        
        # For DUPLICATE, track original/duplicate pair
        if corruption_type == "DUPLICATE":
            exception["original_id"] = entry.get("original_id", "")
            exception["duplicate_id"] = entry.get("duplicate_id", "")
            exception["affected_entity_id"] = entry.get("original_id", "")
        
        # For WRONG_REFERENCE, track the swap
        if corruption_type == "WRONG_REFERENCE":
            exception["correct_reference"] = entry.get("original", "")
            exception["wrong_reference"] = entry.get("corrupted", "")
        
        exceptions.append(exception)
    
    # Write output
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "exception_truth.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for exc in exceptions:
            f.write(json.dumps(exc) + "\n")
    
    # Also write a class distribution summary
    from collections import Counter
    class_dist = Counter(e["exception_class"] for e in exceptions)
    
    summary_path = os.path.join(output_dir, "exception_class_distribution.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_exceptions": len(exceptions),
            "class_distribution": dict(sorted(class_dist.items())),
            "all_possible_classes": ALL_EXCEPTION_CLASSES,
        }, f, indent=2)
    
    print(f"  Generated {len(exceptions)} exception truth records -> {output_path}")
    print(f"  Class distribution:")
    for cls, count in sorted(class_dist.items()):
        print(f"    {cls}: {count}")
    
    return exceptions


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    log_path = os.path.join(base_dir, "data", "raw", "noisy", "corruption_log.jsonl")
    truth_dir = os.path.join(base_dir, "data", "ground_truth")
    generate_exception_truth(log_path, truth_dir)
