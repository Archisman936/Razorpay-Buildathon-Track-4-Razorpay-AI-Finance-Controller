"""
Amount Noise — Step 27

Creates small amount discrepancies with tracked causes:
- FEE_ADJUSTMENT: ±2%
- PARTIAL_SETTLEMENT: ±10%
- TAX_MISMATCH: ±1%
- ROUNDING: ±₹1
- UNKNOWN: ±5%
"""

import random
from decimal import Decimal, ROUND_HALF_UP


def corrupt_amount(amount_str: str, cause: str = None,
                   rng: random.Random = None) -> tuple:
    """
    Apply a small amount discrepancy.
    
    Args:
        amount_str: Original amount as string
        cause: Specific cause or None for random
        rng: Random number generator
    
    Returns:
        Tuple of (corrupted_amount_str, cause)
    """
    if rng is None:
        rng = random.Random()
    
    amount = Decimal(str(amount_str))
    
    if amount <= 0:
        return amount_str, "NONE"
    
    causes = {
        "FEE_ADJUSTMENT": {"max_pct": Decimal("0.02")},
        "PARTIAL_SETTLEMENT": {"max_pct": Decimal("0.10")},
        "TAX_MISMATCH": {"max_pct": Decimal("0.01")},
        "ROUNDING": {"max_amount": Decimal("1.00")},
        "UNKNOWN": {"max_pct": Decimal("0.05")},
    }
    
    if cause is None:
        cause_weights = [0.30, 0.25, 0.20, 0.15, 0.10]
        cause = rng.choices(list(causes.keys()), weights=cause_weights, k=1)[0]
    
    config = causes[cause]
    
    if "max_amount" in config:
        # Fixed amount noise (rounding)
        diff = Decimal(str(rng.uniform(0.01, float(config["max_amount"]))))
    else:
        # Percentage-based noise
        pct = Decimal(str(rng.uniform(0.001, float(config["max_pct"]))))
        diff = amount * pct
    
    diff = diff.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    # Randomly add or subtract
    if rng.random() < 0.5:
        corrupted = amount + diff
    else:
        corrupted = amount - diff
        if corrupted < 0:
            corrupted = amount + diff
    
    return str(corrupted.quantize(Decimal("0.01"))), cause


def apply_amount_noise(records: list, amount_field: str, rate: float,
                       rng: random.Random = None) -> tuple:
    """
    Apply amount noise to records.
    
    Returns:
        Tuple of (modified_records, corruption_log)
    """
    if rng is None:
        rng = random.Random(42)
    
    corruption_log = []
    
    for record in records:
        if rng.random() < rate:
            if amount_field in record and record[amount_field]:
                original = record[amount_field]
                corrupted, cause = corrupt_amount(original, rng=rng)
                record[amount_field] = corrupted
                corruption_log.append({
                    "type": "AMOUNT_NOISE",
                    "field": amount_field,
                    "original": original,
                    "corrupted": corrupted,
                    "cause": cause,
                    "record_id": next(
                        (record[k] for k in record if k.endswith("_id")
                         and not k.startswith("merchant") and not k.startswith("customer")),
                        ""
                    ),
                })
    
    return records, corruption_log
