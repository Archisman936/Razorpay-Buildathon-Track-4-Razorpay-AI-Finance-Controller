"""
Description Noise — Step 25

Applies bank narration/description variations:
- RAZORPAY SETTLEMENT STL1001
- RZP STL1001
- NEFT RZP 1001
- RZP PAYOUT STL-1001
"""

import random
import re

SETTLEMENT_TEMPLATES = [
    "RAZORPAY SETTLEMENT {id}",
    "RZP {id}",
    "NEFT RZP {id}",
    "RZP PAYOUT {id}",
    "RAZORPAY/{id}",
    "NEFT-{id}-RAZORPAY",
    "IMPS RZP {id}",
    "RTGS RAZORPAY {id}",
    "RZP SETL {id}",
    "RAZORPAY PAYOUT {id}",
    "NEFT CR RAZORPAY {id}",
    "RZP-SETTLEMENT-{id}",
]

# How to mangle the settlement ID within the description
ID_MANGLES = [
    lambda sid: sid,                                    # STL_000001
    lambda sid: sid.replace("_", ""),                   # STL000001
    lambda sid: sid.replace("_", "-"),                  # STL-000001
    lambda sid: sid.split("_")[1].lstrip("0") or "0",   # 1
    lambda sid: sid.split("_")[1],                       # 000001
    lambda sid: sid.replace("STL_", ""),                 # 000001
    lambda sid: sid.lower(),                            # stl_000001
]


def corrupt_description(original_desc: str, settlement_id: str = None,
                        rng: random.Random = None) -> str:
    """
    Apply description noise to a bank narration or description.
    
    Args:
        original_desc: Clean description
        settlement_id: Settlement ID if applicable
        rng: Random number generator
    
    Returns:
        Noisy description
    """
    if rng is None:
        rng = random.Random()
    
    if settlement_id:
        # Mangle the settlement ID
        mangled_id = rng.choice(ID_MANGLES)(settlement_id)
        # Pick a new template
        template = rng.choice(SETTLEMENT_TEMPLATES)
        return template.format(id=mangled_id)
    
    # For non-settlement descriptions, apply minor noise
    noise_options = [
        lambda d: d.upper(),
        lambda d: d.lower(),
        lambda d: d.replace(" ", "/"),
        lambda d: d.replace(" ", "-"),
        lambda d: re.sub(r'\s+', ' ', d).strip(),
        lambda d: d[:len(d)//2],  # Truncate
    ]
    
    return rng.choice(noise_options)(original_desc)


def apply_description_noise(records: list, desc_field: str,
                            settlement_id_field: str, rate: float,
                            rng: random.Random = None) -> tuple:
    """
    Apply description noise to a list of records.
    
    Returns:
        Tuple of (modified_records, corruption_log)
    """
    if rng is None:
        rng = random.Random(42)
    
    corruption_log = []
    
    for record in records:
        if rng.random() < rate:
            original = record[desc_field]
            stl_id = record.get(settlement_id_field)
            corrupted = corrupt_description(original, stl_id, rng)
            record[desc_field] = corrupted
            corruption_log.append({
                "type": "DESCRIPTION_NOISE",
                "field": desc_field,
                "original": original,
                "corrupted": corrupted,
                "record_id": record.get("bank_record_id", ""),
            })
    
    return records, corruption_log
