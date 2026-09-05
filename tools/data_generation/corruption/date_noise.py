"""
Date Noise — Step 26

Shifts dates by ±1-3 days to simulate real-world timing differences:
- Settlement: Aug 3 → Bank: Aug 4
- Invoice: Aug 20 → Books: Aug 21
"""

import random
from datetime import datetime, timedelta


def corrupt_date(date_str: str, min_shift: int = 1, max_shift: int = 3,
                 direction: str = "BOTH", rng: random.Random = None) -> str:
    """
    Shift a date string by a small number of days.
    
    Args:
        date_str: ISO date string (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS+05:30)
        min_shift: Minimum days to shift
        max_shift: Maximum days to shift
        direction: FORWARD, BACKWARD, or BOTH
        rng: Random number generator
    
    Returns:
        Shifted date string in same format
    """
    if rng is None:
        rng = random.Random()
    
    # Parse date (handle both formats)
    has_time = "T" in date_str
    if has_time:
        clean = date_str.replace("+05:30", "")
        try:
            dt = datetime.fromisoformat(clean)
        except ValueError:
            return date_str
    else:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return date_str
    
    shift_days = rng.randint(min_shift, max_shift)
    
    if direction == "FORWARD":
        dt = dt + timedelta(days=shift_days)
    elif direction == "BACKWARD":
        dt = dt - timedelta(days=shift_days)
    else:  # BOTH
        if rng.random() < 0.5:
            dt = dt + timedelta(days=shift_days)
        else:
            dt = dt - timedelta(days=shift_days)
    
    if has_time:
        return dt.strftime("%Y-%m-%dT%H:%M:%S+05:30")
    else:
        return dt.strftime("%Y-%m-%d")


def apply_date_noise(records: list, date_fields: list, rate: float,
                     min_shift: int = 1, max_shift: int = 3,
                     direction: str = "BOTH",
                     rng: random.Random = None) -> tuple:
    """
    Apply date noise to records.
    
    Args:
        records: List of record dicts
        date_fields: List of date field names to potentially corrupt
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
            # Pick a random date field to corrupt
            field = rng.choice(date_fields)
            if field in record and record[field]:
                original = record[field]
                corrupted = corrupt_date(original, min_shift, max_shift,
                                         direction, rng)
                record[field] = corrupted
                corruption_log.append({
                    "type": "DATE_NOISE",
                    "field": field,
                    "original": original,
                    "corrupted": corrupted,
                    "record_id": next(
                        (record[k] for k in record if k.endswith("_id") 
                         and not k.startswith("merchant") and not k.startswith("customer")),
                        ""
                    ),
                })
    
    return records, corruption_log
