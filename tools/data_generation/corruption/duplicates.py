"""
Duplicates — Step 29

Adds duplicate records with slight variations:
- BNK_001 and BNK_001_DUP representing the same financial event
"""

import random
import copy


def add_duplicates(records: list, id_field: str, rate: float,
                   rng: random.Random = None) -> tuple:
    """
    Add duplicate records with slight variations.
    
    Args:
        records: List of record dicts
        id_field: Name of the ID field
        rate: Fraction of records to duplicate (0-1)
        rng: Random number generator
    
    Returns:
        Tuple of (records_with_duplicates, duplication_log)
    """
    if rng is None:
        rng = random.Random(42)
    
    num_to_dup = int(len(records) * rate)
    if num_to_dup == 0:
        return records, []
    
    indices_to_dup = rng.sample(range(len(records)), min(num_to_dup, len(records)))
    
    duplication_log = []
    new_records = list(records)
    
    for idx in indices_to_dup:
        original = records[idx]
        duplicate = copy.deepcopy(original)
        
        # Create a duplicate ID
        original_id = duplicate[id_field]
        dup_id = f"{original_id}_DUP"
        duplicate[id_field] = dup_id
        
        # Apply minor variations
        # Slightly different timestamp if present
        for key in duplicate:
            if "date" in key.lower() and duplicate[key] and "T" in str(duplicate[key]):
                # Shift by a few seconds
                date_str = duplicate[key]
                if "+05:30" in date_str:
                    base = date_str.replace("+05:30", "")
                    from datetime import datetime, timedelta
                    try:
                        dt = datetime.fromisoformat(base)
                        dt = dt + timedelta(seconds=rng.randint(1, 300))
                        duplicate[key] = dt.strftime("%Y-%m-%dT%H:%M:%S+05:30")
                    except ValueError:
                        pass
                break
        
        new_records.append(duplicate)
        duplication_log.append({
            "type": "DUPLICATE",
            "original_id": original_id,
            "duplicate_id": dup_id,
            "entity_type": id_field.replace("_id", ""),
        })
    
    return new_records, duplication_log
