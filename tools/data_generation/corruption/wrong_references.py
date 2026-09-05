"""
Wrong References — Step 30

Swaps cross-references to create entity-matching challenges:
- Bank narration points to wrong settlement ID
- Book entry references wrong event
"""

import random


def swap_references(records: list, ref_field: str, rate: float,
                    rng: random.Random = None) -> tuple:
    """
    Swap reference fields between records to create wrong references.
    
    Args:
        records: List of record dicts
        ref_field: Name of the reference field to swap
        rate: Fraction of records to corrupt (0-1)
        rng: Random number generator
    
    Returns:
        Tuple of (modified_records, corruption_log)
    """
    if rng is None:
        rng = random.Random(42)
    
    # Get all records that have the reference field set
    valid_records = [r for r in records if r.get(ref_field)]
    
    if len(valid_records) < 2:
        return records, []
    
    num_to_swap = int(len(valid_records) * rate)
    if num_to_swap < 1:
        return records, []
    
    # Select records to corrupt
    indices = rng.sample(range(len(valid_records)), min(num_to_swap, len(valid_records)))
    
    # Collect all possible reference values
    all_ref_values = list(set(r[ref_field] for r in valid_records if r[ref_field]))
    
    corruption_log = []
    
    for idx in indices:
        record = valid_records[idx]
        original_ref = record[ref_field]
        
        # Pick a different reference value
        candidates = [v for v in all_ref_values if v != original_ref]
        if candidates:
            wrong_ref = rng.choice(candidates)
            record[ref_field] = wrong_ref
            
            # Also corrupt the description if it contains the reference
            if "description" in record and original_ref in str(record["description"]):
                record["description"] = record["description"].replace(
                    str(original_ref), str(wrong_ref)
                )
            
            corruption_log.append({
                "type": "WRONG_REFERENCE",
                "field": ref_field,
                "original": original_ref,
                "corrupted": wrong_ref,
                "record_id": next(
                    (record[k] for k in record if k.endswith("_id")
                     and k != ref_field
                     and not k.startswith("merchant") 
                     and not k.startswith("customer")),
                    ""
                ),
            })
    
    return records, corruption_log
