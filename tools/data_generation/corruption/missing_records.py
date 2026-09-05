"""
Missing Records — Step 28

Removes a percentage of records to create genuine mismatches:
- Settlement exists, bank record missing
- Invoice exists, books entry missing
"""

import random
import copy


def remove_records(records: list, rate: float, id_field: str,
                   rng: random.Random = None) -> tuple:
    """
    Remove a percentage of records to simulate missing data.
    
    Args:
        records: List of record dicts
        rate: Fraction of records to remove (0-1)
        id_field: Name of the ID field for logging
        rng: Random number generator
    
    Returns:
        Tuple of (surviving_records, removal_log)
    """
    if rng is None:
        rng = random.Random(42)
    
    num_to_remove = int(len(records) * rate)
    if num_to_remove == 0:
        return records, []
    
    # Select indices to remove
    indices_to_remove = set(rng.sample(range(len(records)), num_to_remove))
    
    surviving = []
    removal_log = []
    
    for i, record in enumerate(records):
        if i in indices_to_remove:
            removal_log.append({
                "type": "MISSING_RECORD",
                "record_id": record[id_field],
                "entity_type": id_field.replace("_id", ""),
            })
        else:
            surviving.append(record)
    
    return surviving, removal_log
