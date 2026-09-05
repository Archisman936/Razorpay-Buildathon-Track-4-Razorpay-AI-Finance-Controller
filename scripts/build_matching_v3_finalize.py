"""
Matching v3 finalization.

Responsibilities:
    1. Feature quality audit / exact duplicate pruning.
    2. Reference-ambiguity diagnostics.
    3. Grouped split by source_id BEFORE identifier removal.
    4. Verify zero source overlap across train/validation/test.
    5. Keep target/traceability metadata outside final feature CSVs.
    6. Write only:
           data/ml/matching/train.csv
           data/ml/matching/validation.csv
           data/ml/matching/test.csv

Ground truth is used only for diagnostics of the positive-vs-wrong
reference similarity distribution. It is never written as a predictor.
"""

import json
import os
import random
from collections import Counter, defaultdict

import pandas as pd

from feature_audit import (
    audit_features,
    find_exact_duplicates,
)

SEED = 42
random.seed(SEED)

FEATURES_PATH = (
    "scratch/matching_v3/"
    "candidate_pairs_features.json"
)

TRACE_DIR = "scratch/traceability"
OUTPUT_DIR = "data/ml/matching"
AUDIT_DIR = "scratch/matching_v3"

os.makedirs(TRACE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(AUDIT_DIR, exist_ok=True)


# =====================================================================
# LOAD
# =====================================================================

with open(
    FEATURES_PATH,
    encoding="utf-8"
) as f:
    features = json.load(f)

df = pd.DataFrame(features)

id_cols = [
    "pair_id",
    "pair_type",
    "source_id",
    "target_id",
]

label_cols = [
    "label",
]

feat_cols = [
    c for c in df.columns
    if c not in id_cols + label_cols
]


# =====================================================================
# FEATURE QUALITY AUDIT
# =====================================================================

audit_df = audit_features(
    df,
    id_cols,
    label_cols,
)

duplicate_features = find_exact_duplicates(
    df,
    feat_cols,
)

constant_features = audit_df[
    audit_df["constant"]
]["feature"].tolist()

duplicate_remove = [
    duplicate
    for duplicate, original in duplicate_features
]

remove_features = sorted(
    set(constant_features)
    | set(duplicate_remove)
)

print(
    "Constant features:",
    constant_features
)

print(
    "Exact duplicate features:",
    duplicate_features
)

print(
    "Removing:",
    remove_features
)

if remove_features:
    df = df.drop(
        columns=remove_features
    )

audit_df.to_csv(
    os.path.join(
        AUDIT_DIR,
        "feature_quality_matching_v3.csv"
    ),
    index=False,
)


# =====================================================================
# DUPLICATE / LABEL INTEGRITY CHECKS
# =====================================================================

pair_key = list(
    zip(
        df["source_id"],
        df["target_id"],
    )
)

assert len(pair_key) == len(set(pair_key)), (
    "Duplicate source_id/target_id candidate pairs found."
)

conflict_map = {}
conflicts = 0

for _, row in df.iterrows():
    key = (
        row["source_id"],
        row["target_id"],
    )

    label = int(row["label"])

    if (
        key in conflict_map
        and conflict_map[key] != label
    ):
        conflicts += 1

    conflict_map[key] = label

assert conflicts == 0, (
    "Conflicting labels found."
)

assert set(
    df["label"].unique()
).issubset({0, 1}), (
    "Labels must be binary 0/1."
)

print(
    f"Candidate-pair duplicates: 0"
)
print(
    f"Label conflicts: {conflicts}"
)


# =====================================================================
# REFERENCE AMBIGUITY DIAGNOSTICS
# =====================================================================

reference_diagnostics = []

for source_id, group in df.groupby(
    "source_id",
    sort=False,
):

    positives = group[
        group["label"] == 1
    ]

    negatives = group[
        group["label"] == 0
    ]

    if positives.empty:
        continue

    # At most one true candidate is expected per bank record.
    true_similarity = float(
        positives[
            "utr_similarity"
        ].iloc[0]
    )

    if negatives.empty:
        max_wrong_similarity = None
        wrong_near_tie = False
        wrong_overtake = False
    else:
        max_wrong_similarity = float(
            negatives[
                "utr_similarity"
            ].max()
        )

        wrong_near_tie = bool(
            max_wrong_similarity
            >= true_similarity - 0.03
        )

        wrong_overtake = bool(
            max_wrong_similarity
            >= true_similarity
        )

    reference_diagnostics.append({
        "source_id": source_id,
        "true_reference_similarity": true_similarity,
        "max_wrong_reference_similarity": max_wrong_similarity,
        "wrong_within_0.03": wrong_near_tie,
        "wrong_overtakes_or_ties": wrong_overtake,
    })

ref_diag_df = pd.DataFrame(
    reference_diagnostics
)

ref_diag_path = os.path.join(
    AUDIT_DIR,
    "reference_ambiguity_diagnostics.csv"
)

ref_diag_df.to_csv(
    ref_diag_path,
    index=False,
)

print(
    "\nREFERENCE AMBIGUITY DIAGNOSTICS"
)

if not ref_diag_df.empty:

    print(
        "Residual positives with wrong reference within 0.03:",
        int(
            ref_diag_df[
                "wrong_within_0.03"
            ].sum()
        )
    )

    print(
        "Residual positives with wrong reference >= true:",
        int(
            ref_diag_df[
                "wrong_overtakes_or_ties"
            ].sum()
        )
    )

    print(
        "Total residual positives:",
        len(ref_diag_df)
    )

    print(
        "True UTR similarity summary:"
    )
    print(
        ref_diag_df[
            "true_reference_similarity"
        ].describe()
    )

    wrong_series = ref_diag_df[
        "max_wrong_reference_similarity"
    ].dropna()

    if not wrong_series.empty:
        print(
            "Max wrong UTR similarity summary:"
        )
        print(
            wrong_series.describe()
        )


# =====================================================================
# NEGATIVE TYPE DIAGNOSTICS
# =====================================================================

negative_breakdown = Counter(
    df.loc[
        df["label"] == 0,
        "negative_type",
    ].fillna("unknown")
)

print(
    "\nNEGATIVE BREAKDOWN"
)

for key, value in sorted(
    negative_breakdown.items()
):
    print(
        f"  {key}: {value}"
    )


# =====================================================================
# AMOUNT / DATE DIAGNOSTICS
# =====================================================================

print(
    "\nAMOUNT / DATE DIAGNOSTICS"
)

positive_rows = df[
    df["label"] == 1
]
negative_rows = df[
    df["label"] == 0
]

if not positive_rows.empty:

    print(
        "Positive relative amount difference:"
    )

    print(
        positive_rows[
            "relative_amount_difference"
        ].describe()
    )

if not negative_rows.empty:

    print(
        "Negative relative amount difference:"
    )

    print(
        negative_rows[
            "relative_amount_difference"
        ].describe()
    )

if not positive_rows.empty:

    print(
        "Positive date difference:"
    )

    print(
        positive_rows[
            "date_difference_days"
        ].describe()
    )

if not negative_rows.empty:

    print(
        "Negative date difference:"
    )

    print(
        negative_rows[
            "date_difference_days"
        ].describe()
    )


# =====================================================================
# CANDIDATE COUNT DIAGNOSTICS
# =====================================================================

candidate_count_summary = (
    df.groupby("source_id")
    .size()
    .describe()
)

print(
    "\nCANDIDATE COUNT PER BANK RECORD"
)
print(
    candidate_count_summary
)


# =====================================================================
# GROUPED SPLIT BY source_id
# =====================================================================

source_ids = df[
    "source_id"
].unique().tolist()

shuffle_rng = random.Random(SEED)
shuffle_rng.shuffle(
    source_ids
)

rows_per_source = (
    df.groupby("source_id")
    .size()
    .to_dict()
)

total_rows = len(df)

target_train = 0.70 * total_rows
target_validation = 0.15 * total_rows

split_of_source = {}
running = {
    "train": 0,
    "validation": 0,
    "test": 0,
}

for source_id in source_ids:

    n_rows = rows_per_source[
        source_id
    ]

    if (
        running["train"] + n_rows
        <= target_train
        or running["train"] == 0
    ):

        split_of_source[
            source_id
        ] = "train"

        running["train"] += n_rows

    elif (
        running["validation"] + n_rows
        <= target_validation
        or running["validation"] == 0
    ):

        split_of_source[
            source_id
        ] = "validation"

        running["validation"] += n_rows

    else:

        split_of_source[
            source_id
        ] = "test"

        running["test"] += n_rows


df["split"] = df[
    "source_id"
].map(split_of_source)

print(
    "\nSPLIT SIZES"
)
print(
    df["split"].value_counts()
)

print(
    "\nPOSITIVES PER SPLIT"
)
print(
    df.groupby("split")["label"].sum()
)

# ---------------------------------------------------------------------
# Verify source isolation BEFORE removing source_id.
# ---------------------------------------------------------------------
source_sets = {
    split: set(
        df.loc[
            df["split"] == split,
            "source_id",
        ]
    )
    for split in [
        "train",
        "validation",
        "test",
    ]
}

assert not (
    source_sets["train"]
    & source_sets["validation"]
)

assert not (
    source_sets["train"]
    & source_sets["test"]
)

assert not (
    source_sets["validation"]
    & source_sets["test"]
)

print(
    "\nsource_id isolation: VERIFIED (zero overlap)"
)

# ---------------------------------------------------------------------
# Settlement reuse is allowed because multiple bank observations can
# legitimately refer to the same settlement in a multi-source setting.
# We only report it.
# ---------------------------------------------------------------------
settlement_sets = {
    split: set(
        df.loc[
            df["split"] == split,
            "target_id",
        ]
    )
    for split in [
        "train",
        "validation",
        "test",
    ]
}

print(
    "target_id reuse -- "
    f"train/val={len(settlement_sets['train'] & settlement_sets['validation'])}, "
    f"train/test={len(settlement_sets['train'] & settlement_sets['test'])}, "
    f"val/test={len(settlement_sets['validation'] & settlement_sets['test'])}"
)


# =====================================================================
# TRACEABILITY FILE
# =====================================================================

traceability = df[
    id_cols
    + [
        "split",
        "label",
    ]
].copy()

trace_path = os.path.join(
    TRACE_DIR,
    "matching_v3_pair_id_map.csv"
)

traceability.to_csv(
    trace_path,
    index=False,
)


# =====================================================================
# FINAL DATASET: REMOVE IDENTIFIERS
# =====================================================================

feature_cols = [
    c for c in df.columns
    if c not in (
        id_cols
        + [
            "split",
            "negative_type",
        ]
    )
]

# The label remains intentionally because it is the supervised target.

for split in [
    "train",
    "validation",
    "test",
]:

    out = df.loc[
        df["split"] == split,
        feature_cols,
    ].copy()

    output_path = os.path.join(
        OUTPUT_DIR,
        f"{split}.csv"
    )

    out.to_csv(
        output_path,
        index=False,
    )

    print(
        f"Saved {output_path} shape={out.shape}"
    )


# =====================================================================
# FINAL SANITY SUMMARY
# =====================================================================

final_feature_count = len(
    [
        c for c in feature_cols
        if c != "label"
    ]
)

print(
    "\n" + "=" * 90
)
print(
    "MATCHING V3 DATASET FINAL REPORT"
)
print(
    "=" * 90
)

print(
    f"Total rows              : {len(df)}"
)
print(
    f"Positive rows           : {int(df['label'].sum())}"
)
print(
    f"Negative rows           : {int((df['label'] == 0).sum())}"
)
print(
    f"Feature count           : {final_feature_count}"
)
print(
    f"Train shape             : {tuple(df[df['split'] == 'train'][feature_cols].shape)}"
)
print(
    f"Validation shape        : {tuple(df[df['split'] == 'validation'][feature_cols].shape)}"
)
print(
    f"Test shape              : {tuple(df[df['split'] == 'test'][feature_cols].shape)}"
)
print(
    f"Conflicting labels      : {conflicts}"
)
print(
    "Source grouping         : VERIFIED"
)
print(
    f"Traceability            : {trace_path}"
)
print(
    "Final outputs           : data/ml/matching/{train,validation,test}.csv"
)
print(
    "=" * 90
)
print(
    "READY_FOR_RECONCILIATION_MODEL_TRAINING"
)
print(
    "=" * 90
)
