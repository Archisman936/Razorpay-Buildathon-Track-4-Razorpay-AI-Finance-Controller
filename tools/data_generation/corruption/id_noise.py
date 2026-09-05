"""
ID Noise — Step 24

Applies format variations to entity IDs:
- ORD-000123 (dash separator)
- ORD000123 (no separator)
- ORD/000123 (slash separator)
- ord_000123 (lowercase)
- ORDER_000123 (prefix variation)
"""

import random

# Mapping of standard prefix → alternative prefixes
PREFIX_VARIATIONS = {
    "ORD": ["ORD", "ORDER", "O"],
    "INV": ["INV", "INVOICE", "I"],
    "PAY": ["PAY", "PAYMENT", "P"],
    "STL": ["STL", "SETTLEMENT", "S"],
    "BNK": ["BNK", "BANK", "B"],
    "FEE": ["FEE", "F"],
    "REF": ["REF", "REFUND", "R"],
    "LED": ["LED", "LEDGER", "L"],
    "GST": ["GST", "G"],
    "ADJ": ["ADJ", "ADJUSTMENT", "A"],
}

SEPARATOR_STRATEGIES = {
    "DASH_SEPARATOR": "-",
    "NO_SEPARATOR": "",
    "SLASH_SEPARATOR": "/",
    "UNDERSCORE": "_",
}


def corrupt_id(original_id: str, strategy: str = None) -> str:
    """
    Apply ID format noise to an entity ID.
    
    Args:
        original_id: Clean ID like 'ORD_000123'
        strategy: Specific strategy or None for random
    
    Returns:
        Noisy ID like 'ORD-000123' or 'ORDER000123'
    """
    if "_" not in original_id:
        return original_id
    
    parts = original_id.split("_", 1)
    prefix = parts[0]
    number = parts[1]
    
    if strategy is None:
        strategy = random.choice([
            "DASH_SEPARATOR", "NO_SEPARATOR", "SLASH_SEPARATOR",
            "LOWERCASE", "PREFIX_VARIATION"
        ])
    
    if strategy == "LOWERCASE":
        sep = random.choice(["_", "-", ""])
        return f"{prefix.lower()}{sep}{number}"
    
    elif strategy == "PREFIX_VARIATION":
        alt_prefixes = PREFIX_VARIATIONS.get(prefix, [prefix])
        new_prefix = random.choice(alt_prefixes)
        sep = random.choice(["_", "-", "", "/"])
        return f"{new_prefix}{sep}{number}"
    
    elif strategy in SEPARATOR_STRATEGIES:
        sep = SEPARATOR_STRATEGIES[strategy]
        return f"{prefix}{sep}{number}"
    
    return original_id


def apply_id_noise(records: list, id_field: str, rate: float,
                   rng: random.Random = None) -> tuple:
    """
    Apply ID noise to a list of records.
    
    Args:
        records: List of record dicts
        id_field: Name of the ID field to corrupt
        rate: Probability of corruption per record
        rng: Random number generator
    
    Returns:
        Tuple of (modified_records, corruption_log)
    """
    if rng is None:
        rng = random.Random(42)
    
    corruption_log = []
    
    for record in records:
        if rng.random() < rate:
            original = record[id_field]
            corrupted = corrupt_id(original)
            record[id_field] = corrupted
            corruption_log.append({
                "type": "ID_NOISE",
                "field": id_field,
                "original": original,
                "corrupted": corrupted,
                "record_id": original,
            })
    
    return records, corruption_log
