"""
Matching v3 feature engineering.

All predictor features are generated from:
    observed bank record + current candidate settlement

No label / event_links / ground-truth target is used to calculate feature
values.

Adds:
    best_vs_second_best_reference_gap

The ranking features are computed per bank record from the complete
candidate set actually present in the matching dataset.
"""

import json
from collections import defaultdict

from common import (
    date_only,
    days_between,
    load_table,
    normalize_id,
    str_similarity,
    to_float,
    token_overlap,
)

BANK_PATH = (
    "scratch/matching_v3/"
    "bank_records_matching_observed.jsonl"
)
CANDIDATE_PATH = (
    "scratch/matching_v3/"
    "candidate_pairs_raw.json"
)
OUTPUT_PATH = (
    "scratch/matching_v3/"
    "candidate_pairs_features.json"
)


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


bank_records = load_jsonl(
    BANK_PATH
)

bank_by_id = {
    b["bank_record_id"]: b
    for b in bank_records
}

settlements = load_table(
    "settlements"
)

merchants = load_table(
    "merchants"
)

stl_by_id = {
    s["settlement_id"]: s
    for s in settlements
}

merchant_by_id = {
    m["merchant_id"]: m
    for m in merchants
}

candidates = json.load(
    open(CANDIDATE_PATH, encoding="utf-8")
)


# =====================================================================
# BASE PAIR FEATURES
# =====================================================================

base_rows = {}

for c in candidates:

    bank_id = c["source_id"]
    stl_id = c["target_id"]

    b = bank_by_id[bank_id]
    s = stl_by_id[stl_id]

    bank_amount = to_float(
        b.get("amount")
    )

    net_amount = to_float(
        s.get("net_amount")
    )

    gross_amount = to_float(
        s.get("gross_amount")
    )

    amount_difference = (
        bank_amount - net_amount
        if (
            bank_amount is not None
            and net_amount is not None
        )
        else None
    )

    absolute_amount_difference = (
        abs(amount_difference)
        if amount_difference is not None
        else None
    )

    relative_amount_difference = (
        absolute_amount_difference / abs(net_amount)
        if (
            absolute_amount_difference is not None
            and net_amount not in (None, 0)
        )
        else None
    )

    amount_ratio = (
        bank_amount / net_amount
        if (
            bank_amount is not None
            and net_amount not in (None, 0)
        )
        else None
    )

    exact_amount_match = int(
        absolute_amount_difference is not None
        and absolute_amount_difference < 0.01
    )

    absolute_amount_difference_vs_gross = (
        abs(bank_amount - gross_amount)
        if (
            bank_amount is not None
            and gross_amount is not None
        )
        else None
    )

    bank_date = date_only(
        b.get("transaction_date")
    )

    value_date = date_only(
        b.get("value_date")
    )

    settlement_date = date_only(
        s.get("settlement_date")
    )

    date_difference_days = days_between(
        bank_date,
        settlement_date
    )

    value_date_difference_days = days_between(
        value_date,
        settlement_date
    )

    bank_reference = normalize_id(
        b.get("reference")
    )

    candidate_utr = normalize_id(
        s.get("utr")
    )

    reference_exact_match = int(
        bool(bank_reference)
        and bool(candidate_utr)
        and bank_reference == candidate_utr
    )

    utr_similarity = str_similarity(
        bank_reference,
        candidate_utr
    )

    # This feature is still legitimate: it searches the observed bank
    # description for the CURRENT candidate's settlement id.
    settlement_id_in_description = int(
        bool(s.get("settlement_id"))
        and str(s["settlement_id"]).upper()
        in str(
            b.get("description") or ""
        ).upper()
    )

    description_token_overlap = token_overlap(
        b.get("description"),
        (
            f"{s.get('settlement_id', '')} settlement "
            f"{s.get('utr', '')}"
        )
    )

    merchant_match = int(
        b.get("merchant_id")
        ==
        s.get("merchant_id")
    )

    transaction_type_is_credit = int(
        b.get("transaction_type") == "CREDIT"
    )

    # Retain categorical context exactly as observable.
    bank_category = b.get("category")

    payment_count = s.get(
        "payment_count"
    )

    base_rows[(
        bank_id,
        stl_id
    )] = {

        "pair_id":
            c["pair_id"],

        "pair_type":
            c["pair_type"],

        "source_id":
            bank_id,

        "target_id":
            stl_id,

        "label":
            int(c["label"]),

        "negative_type":
            c.get("negative_type"),

        "bank_amount":
            bank_amount,

        "settlement_net_amount":
            net_amount,

        "settlement_gross_amount":
            gross_amount,

        "settlement_fee_amount":
            to_float(s.get("total_fees")),

        "settlement_fee_tax_amount":
            to_float(s.get("total_fee_tax")),

        "settlement_refund_amount":
            to_float(s.get("total_refunds")),

        "amount_difference":
            amount_difference,

        "absolute_amount_difference":
            absolute_amount_difference,

        "relative_amount_difference":
            relative_amount_difference,

        "amount_ratio":
            amount_ratio,

        "exact_amount_match":
            exact_amount_match,

        "absolute_amount_difference_vs_gross":
            absolute_amount_difference_vs_gross,

        "date_difference_days":
            date_difference_days,

        "value_date_difference_days":
            value_date_difference_days,

        "same_day":
            int(date_difference_days == 0),

        "within_1_day":
            int(
                date_difference_days is not None
                and date_difference_days <= 1
            ),

        "within_3_days":
            int(
                date_difference_days is not None
                and date_difference_days <= 3
            ),

        "within_7_days":
            int(
                date_difference_days is not None
                and date_difference_days <= 7
            ),

        "reference_exact_match":
            reference_exact_match,

        "utr_similarity":
            utr_similarity,

        "settlement_id_in_description":
            settlement_id_in_description,

        "description_token_overlap":
            description_token_overlap,

        "merchant_match":
            merchant_match,

        "transaction_type_is_credit":
            transaction_type_is_credit,

        "bank_category":
            bank_category,

        "payment_count":
            payment_count,
    }


# =====================================================================
# CANDIDATE-SET RANKING FEATURES
# =====================================================================

by_source = defaultdict(list)

for key, row in base_rows.items():
    by_source[key[0]].append(row)

for bank_id, rows in by_source.items():

    candidate_count = len(rows)

    amount_sorted = sorted(
        rows,
        key=lambda r: (
            r["absolute_amount_difference"]
            if r["absolute_amount_difference"] is not None
            else float("inf"),
            r["target_id"],
        ),
    )

    date_sorted = sorted(
        rows,
        key=lambda r: (
            r["date_difference_days"]
            if r["date_difference_days"] is not None
            else float("inf"),
            r["target_id"],
        ),
    )

    reference_sorted = sorted(
        rows,
        key=lambda r: (
            -r["utr_similarity"],
            r["target_id"],
        ),
    )

    amount_rank = {
        id(row): idx + 1
        for idx, row in enumerate(amount_sorted)
    }

    date_rank = {
        id(row): idx + 1
        for idx, row in enumerate(date_sorted)
    }

    reference_rank = {
        id(row): idx + 1
        for idx, row in enumerate(reference_sorted)
    }

    best_amount = (
        amount_sorted[0][
            "absolute_amount_difference"
        ]
        if amount_sorted
        else None
    )

    second_amount = (
        amount_sorted[1][
            "absolute_amount_difference"
        ]
        if candidate_count > 1
        else None
    )

    best_date = (
        date_sorted[0][
            "date_difference_days"
        ]
        if date_sorted
        else None
    )

    second_date = (
        date_sorted[1][
            "date_difference_days"
        ]
        if candidate_count > 1
        else None
    )

    best_reference = (
        reference_sorted[0][
            "utr_similarity"
        ]
        if reference_sorted
        else None
    )

    second_reference = (
        reference_sorted[1][
            "utr_similarity"
        ]
        if candidate_count > 1
        else None
    )

    amount_gap = (
        second_amount - best_amount
        if (
            best_amount is not None
            and second_amount is not None
        )
        else None
    )

    date_gap = (
        second_date - best_date
        if (
            best_date is not None
            and second_date is not None
        )
        else None
    )

    reference_gap = (
        best_reference - second_reference
        if (
            best_reference is not None
            and second_reference is not None
        )
        else None
    )

    for row in rows:

        row["candidate_count"] = candidate_count

        row[
            "candidate_rank_by_amount"
        ] = amount_rank[id(row)]

        row[
            "candidate_rank_by_date"
        ] = date_rank[id(row)]

        row[
            "candidate_rank_by_reference"
        ] = reference_rank[id(row)]

        row[
            "is_best_amount_candidate"
        ] = int(
            amount_rank[id(row)] == 1
        )

        row[
            "is_best_date_candidate"
        ] = int(
            date_rank[id(row)] == 1
        )

        row[
            "is_best_reference_candidate"
        ] = int(
            reference_rank[id(row)] == 1
        )

        row[
            "best_vs_second_best_amount_gap"
        ] = amount_gap

        row[
            "best_vs_second_best_date_gap"
        ] = date_gap

        row[
            "best_vs_second_best_reference_gap"
        ] = reference_gap


feature_rows = list(
    base_rows.values()
)

with open(
    OUTPUT_PATH,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        feature_rows,
        f,
        indent=2,
        sort_keys=True,
    )

feature_columns = [
    key
    for key in feature_rows[0].keys()
    if key not in (
        "pair_id",
        "pair_type",
        "source_id",
        "target_id",
        "label",
        "negative_type",
    )
]

print(
    f"Built features for {len(feature_rows)} pairs."
)
print(
    f"Feature count before quality pruning: {len(feature_columns)}"
)
print(
    feature_columns
)
print(
    f"Saved -> {OUTPUT_PATH}"
)
