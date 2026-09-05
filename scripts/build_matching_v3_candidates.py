"""
Matching v3 candidate generation.

Main fix vs v2:
    Build genuinely reference-confusable WRONG candidates from the real
    settlement table. No settlement UTR is fabricated or modified.

Important:
    Ground truth is used only to identify the positive pair and to exclude
    it while sampling hard negatives. Ground truth is NEVER written into
    predictor features; features are generated later from bank observation
    + candidate settlement only.

Candidate families:
    - hard_amount_close
    - hard_date_close_amount_plausible
    - hard_both_close
    - hard_reference_near_tie
    - hard_reference_overtake
    - hard_multi_signal
    - easy
"""

import hashlib
import json
import random
from collections import Counter, defaultdict

from common import (
    load_ground_truth,
    load_table,
    date_only,
    days_between,
    normalize_id,
    str_similarity,
    to_float,
)

SEED = 42
random.seed(SEED)

BANK_PATH = "scratch/matching_v3/bank_records_matching_observed.jsonl"
OUTPUT_PATH = "scratch/matching_v3/candidate_pairs_raw.json"

BLOCK_WINDOW_DAYS = 25
REFERENCE_NEAR_TIE_TOL = 0.03


def seeded_rng(record_id, salt):
    h = hashlib.sha256(f"{record_id}:{salt}:{SEED}".encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def auto_resolve(bank_rec, stl_rec):
    """Production-stage rule: exact amount AND exact normalized reference."""
    bank_amount = to_float(bank_rec.get("amount"))
    settlement_amount = to_float(stl_rec.get("net_amount"))

    amt_exact = (
        bank_amount is not None
        and settlement_amount is not None
        and abs(bank_amount - settlement_amount) < 0.01
    )

    bank_ref = normalize_id(bank_rec.get("reference"))
    stl_ref = normalize_id(stl_rec.get("utr"))

    ref_exact = (
        bool(bank_ref)
        and bool(stl_ref)
        and bank_ref == stl_ref
    )

    return amt_exact and ref_exact


def add_candidate(container, seen, bank_id, stl_id, label, neg_type=None):
    key = (bank_id, stl_id)

    if key in seen:
        return False

    container.append({
        "pair_id": f"MATCH_{bank_id}__{stl_id}",
        "pair_type": "BANK_SETTLEMENT",
        "source_id": bank_id,
        "target_id": stl_id,
        "label": int(label),
        "negative_type": neg_type,
    })

    seen.add(key)
    return True


bank_records = load_jsonl(BANK_PATH)
bank_by_id = {
    b["bank_record_id"]: b
    for b in bank_records
}

settlements = load_table("settlements")
stl_by_id = {
    s["settlement_id"]: s
    for s in settlements
}

# -------------------------------------------------------------------------
# Ground truth used only for positive supervision / exclusion.
# -------------------------------------------------------------------------
event_links = load_ground_truth("event_links")

positive_pairs = set()
for r in event_links:
    if (
        r.get("relationship") == "CORRESPONDS_TO"
        and r.get("source_type") == "bank_record"
        and r.get("target_type") == "settlement"
    ):
        positive_pairs.add(
            (r["source_id"], r["target_id"])
        )

pos_by_bank = {
    bank_id: settlement_id
    for bank_id, settlement_id in positive_pairs
}

settlements_by_merchant = defaultdict(list)
for s in settlements:
    settlements_by_merchant[
        s["merchant_id"]
    ].append(s)

all_merchants = list(
    settlements_by_merchant.keys()
)

candidate_rows = []
seen_pairs = set()
excluded_auto_resolved = []

# Diagnostics specifically for reference ambiguity.
reference_diagnostics = []

for b in bank_records:

    bank_id = b["bank_record_id"]
    merchant_id = b.get("merchant_id")
    bank_date = date_only(
        b.get("transaction_date")
    )
    bank_amount = to_float(
        b.get("amount")
    )
    bank_reference = normalize_id(
        b.get("reference")
    )

    true_stl = pos_by_bank.get(bank_id)

    # ---------------------------------------------------------------
    # Positive: residual-only ML pool.
    # ---------------------------------------------------------------
    if true_stl is not None:

        true_rec = stl_by_id[true_stl]

        if auto_resolve(b, true_rec):

            excluded_auto_resolved.append(
                bank_id
            )

        else:

            add_candidate(
                candidate_rows,
                seen_pairs,
                bank_id,
                true_stl,
                1,
                None,
            )

    # ---------------------------------------------------------------
    # Build real WRONG candidate descriptors.
    # ---------------------------------------------------------------
    same_merchant = []

    for s in settlements_by_merchant.get(
        merchant_id,
        []
    ):

        sid = s["settlement_id"]

        if sid == true_stl:
            continue

        if auto_resolve(b, s):
            continue

        settlement_date = date_only(
            s.get("settlement_date")
        )

        d = days_between(
            bank_date,
            settlement_date
        )

        net = to_float(
            s.get("net_amount")
        )

        if (
            bank_amount is not None
            and net not in (None, 0)
        ):
            rel_amount_diff = (
                abs(bank_amount - net)
                / abs(net)
            )
        else:
            rel_amount_diff = None

        ref_sim = str_similarity(
            bank_reference,
            normalize_id(s.get("utr"))
        )

        same_merchant.append({
            "stl_id": sid,
            "date_diff": d,
            "rel_amt_diff": rel_amount_diff,
            "ref_sim": ref_sim,
            "merchant_match": 1,
        })

    # Full settlement pool is necessary for authentic reference-confusable
    # negatives because the UTR format is shared across merchants/banks.
    global_reference_pool = []

    for s in settlements:

        sid = s["settlement_id"]

        if sid == true_stl:
            continue

        if auto_resolve(b, s):
            continue

        ref_sim = str_similarity(
            bank_reference,
            normalize_id(s.get("utr"))
        )

        settlement_date = date_only(
            s.get("settlement_date")
        )

        d = days_between(
            bank_date,
            settlement_date
        )

        net = to_float(
            s.get("net_amount")
        )

        if (
            bank_amount is not None
            and net not in (None, 0)
        ):
            rel_amount_diff = (
                abs(bank_amount - net)
                / abs(net)
            )
        else:
            rel_amount_diff = None

        global_reference_pool.append({
            "stl_id": sid,
            "date_diff": d,
            "rel_amt_diff": rel_amount_diff,
            "ref_sim": ref_sim,
            "merchant_match": int(
                s.get("merchant_id") == merchant_id
            ),
        })

    # ---------------------------------------------------------------
    # Negative family A: amount-close.
    # ---------------------------------------------------------------
    amount_close = sorted(
        [
            x for x in same_merchant
            if (
                x["rel_amt_diff"] is not None
                and x["rel_amt_diff"] <= 0.15
            )
        ],
        key=lambda x: (
            x["rel_amt_diff"],
            x["date_diff"] if x["date_diff"] is not None else 10**9
        ),
    )

    for x in amount_close[:2]:
        add_candidate(
            candidate_rows,
            seen_pairs,
            bank_id,
            x["stl_id"],
            0,
            "hard_amount_close",
        )

    # ---------------------------------------------------------------
    # Negative family B: date-close + amount-plausible.
    # ---------------------------------------------------------------
    date_close = sorted(
        [
            x for x in same_merchant
            if (
                x["date_diff"] is not None
                and x["date_diff"] <= BLOCK_WINDOW_DAYS
                and x["rel_amt_diff"] is not None
                and x["rel_amt_diff"] <= 0.50
            )
        ],
        key=lambda x: (
            x["date_diff"],
            x["rel_amt_diff"]
        ),
    )

    for x in date_close[:2]:
        add_candidate(
            candidate_rows,
            seen_pairs,
            bank_id,
            x["stl_id"],
            0,
            "hard_date_close_amount_plausible",
        )

    # ---------------------------------------------------------------
    # Negative family C: both close.
    # ---------------------------------------------------------------
    both_close = sorted(
        [
            x for x in same_merchant
            if (
                x["date_diff"] is not None
                and x["date_diff"] <= BLOCK_WINDOW_DAYS
                and x["rel_amt_diff"] is not None
                and x["rel_amt_diff"] <= 0.30
            )
        ],
        key=lambda x: (
            x["date_diff"]
            + 10.0 * x["rel_amt_diff"]
        ),
    )

    for x in both_close[:2]:
        add_candidate(
            candidate_rows,
            seen_pairs,
            bank_id,
            x["stl_id"],
            0,
            "hard_both_close",
        )

    # ---------------------------------------------------------------
    # MAIN FIX: genuinely reference-confusable wrong candidates.
    # ---------------------------------------------------------------
    if true_stl is not None:

        true_rec = stl_by_id[true_stl]
        true_ref_sim = str_similarity(
            bank_reference,
            normalize_id(
                true_rec.get("utr")
            )
        )

        reference_diagnostics.append({
            "bank_id": bank_id,
            "true_reference_similarity": true_ref_sim,
        })

        wrong_pool = global_reference_pool

        # -----------------------------------------------------------
        # D1: Near-tie against the true candidate.
        # Choose several real wrong settlements with similarity close
        # to the true candidate.
        # -----------------------------------------------------------
        near_ties = [
            x for x in wrong_pool
            if abs(
                x["ref_sim"] - true_ref_sim
            ) <= REFERENCE_NEAR_TIE_TOL
        ]

        near_ties.sort(
            key=lambda x: (
                abs(
                    x["ref_sim"]
                    - true_ref_sim
                ),
                -x["ref_sim"]
            )
        )

        # Take several distinct real candidates.
        for x in near_ties[:3]:
            add_candidate(
                candidate_rows,
                seen_pairs,
                bank_id,
                x["stl_id"],
                0,
                "hard_reference_near_tie",
            )

        # -----------------------------------------------------------
        # D2: Reference overtake.
        # A wrong REAL settlement whose similarity is >= true score.
        # -----------------------------------------------------------
        overtakes = [
            x for x in wrong_pool
            if x["ref_sim"] >= true_ref_sim
        ]

        overtakes.sort(
            key=lambda x: (
                -x["ref_sim"],
                x["stl_id"],
            )
        )

        for x in overtakes[:2]:
            add_candidate(
                candidate_rows,
                seen_pairs,
                bank_id,
                x["stl_id"],
                0,
                "hard_reference_overtake",
            )

        # -----------------------------------------------------------
        # D3: Same-merchant reference near-tie.
        # Gives the matcher an especially realistic case where entity
        # context agrees with the candidate while reference is close.
        # -----------------------------------------------------------
        same_merchant_ref_ties = [
            x for x in same_merchant
            if abs(
                x["ref_sim"] - true_ref_sim
            ) <= REFERENCE_NEAR_TIE_TOL
        ]

        same_merchant_ref_ties.sort(
            key=lambda x: (
                abs(
                    x["ref_sim"]
                    - true_ref_sim
                ),
                x["date_diff"] if x["date_diff"] is not None else 10**9,
                x["rel_amt_diff"] if x["rel_amt_diff"] is not None else 10**9,
            )
        )

        for x in same_merchant_ref_ties[:2]:
            add_candidate(
                candidate_rows,
                seen_pairs,
                bank_id,
                x["stl_id"],
                0,
                "hard_reference_same_merchant",
            )

        # -----------------------------------------------------------
        # D4: Multi-signal hardness.
        # Observable-at-inference-time conditions are used to find a
        # wrong candidate that is close on reference + date + amount.
        # -----------------------------------------------------------
        multi_signal = [
            x for x in same_merchant
            if (
                x["date_diff"] is not None
                and x["date_diff"] <= BLOCK_WINDOW_DAYS
                and x["rel_amt_diff"] is not None
                and x["rel_amt_diff"] <= 0.30
                and abs(
                    x["ref_sim"] - true_ref_sim
                ) <= 0.08
            )
        ]

        multi_signal.sort(
            key=lambda x: (
                abs(
                    x["ref_sim"] - true_ref_sim
                ),
                x["date_diff"],
                x["rel_amt_diff"],
            )
        )

        for x in multi_signal[:2]:
            add_candidate(
                candidate_rows,
                seen_pairs,
                bank_id,
                x["stl_id"],
                0,
                "hard_multi_signal",
            )

    # ---------------------------------------------------------------
    # Easy negative: one different-merchant real settlement.
    # ---------------------------------------------------------------
    rng = seeded_rng(bank_id, "easy")
    other_merchants = [
        m for m in all_merchants
        if m != merchant_id
    ]
    rng.shuffle(other_merchants)

    for merchant in other_merchants:
        pool = settlements_by_merchant.get(
            merchant,
            []
        )
        if not pool:
            continue

        candidate = pool[
            rng.randrange(len(pool))
        ]

        if candidate["settlement_id"] == true_stl:
            continue

        if auto_resolve(b, candidate):
            continue

        add_candidate(
            candidate_rows,
            seen_pairs,
            bank_id,
            candidate["settlement_id"],
            0,
            "easy",
        )
        break


# -------------------------------------------------------------------------
# Integrity checks.
# -------------------------------------------------------------------------
label_values = [
    r["label"]
    for r in candidate_rows
]

conflicts = 0
pair_label = {}

for r in candidate_rows:
    key = (
        r["source_id"],
        r["target_id"]
    )

    if (
        key in pair_label
        and pair_label[key] != r["label"]
    ):
        conflicts += 1

    pair_label[key] = r["label"]

assert conflicts == 0, "Conflicting labels found."

# Exact duplicate candidate pairs should never occur.
assert len(pair_label) == len(candidate_rows)

import os
os.makedirs(
    "scratch/matching_v3",
    exist_ok=True
)

with open(
    OUTPUT_PATH,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        candidate_rows,
        f,
        indent=2,
        sort_keys=True,
    )

neg_breakdown = Counter(
    r["negative_type"]
    for r in candidate_rows
    if r["label"] == 0
)

print(
    f"Positives excluded as deterministic auto-resolve: "
    f"{len(excluded_auto_resolved)} / {len(positive_pairs)}"
)

print(
    f"Total candidate pairs: {len(candidate_rows)}"
)
print(
    f"  positives: {sum(label_values)}"
)
print(
    f"  negatives: {len(label_values) - sum(label_values)}"
)
print(
    "Negative breakdown:"
)
for k, v in sorted(neg_breakdown.items()):
    print(
        f"  {k}: {v}"
    )

print(
    f"Conflicting labels: {conflicts}"
)
print(
    f"Saved -> {OUTPUT_PATH}"
)
