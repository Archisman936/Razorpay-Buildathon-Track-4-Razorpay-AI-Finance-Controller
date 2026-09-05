"""Build the reconciliation model's feature rows from a bank + candidate set.

The on-disk feature_schema.json is the runtime column contract.
Formulas follow scripts/build_matching_v3_features.py.
"""

from __future__ import annotations

from backend.app.ml.model_loader import ModelLoader, get_model_loader
from backend.app.services.reconciliation.metrics import (
    days_between,
    normalize_id,
    str_similarity,
    to_float,
    token_overlap,
)


def pair_base_features(bank: dict, settlement: dict) -> dict:
    bank_amount = to_float(bank.get("amount"))
    net_amount = to_float(settlement.get("net_amount"))
    gross_amount = to_float(settlement.get("gross_amount"))

    amount_difference = (
        bank_amount - net_amount
        if bank_amount is not None and net_amount is not None
        else None
    )
    absolute_amount_difference = (
        abs(amount_difference) if amount_difference is not None else None
    )
    relative_amount_difference = (
        absolute_amount_difference / abs(net_amount)
        if absolute_amount_difference is not None and net_amount not in (None, 0)
        else None
    )
    amount_ratio = (
        bank_amount / net_amount
        if bank_amount is not None and net_amount not in (None, 0)
        else None
    )
    exact_amount_match = int(
        absolute_amount_difference is not None and absolute_amount_difference < 0.01
    )
    absolute_amount_difference_vs_gross = (
        abs(bank_amount - gross_amount)
        if bank_amount is not None and gross_amount is not None
        else None
    )

    date_difference_days = days_between(
        bank.get("transaction_date"),
        settlement.get("settlement_date"),
    )
    value_date_difference_days = days_between(
        bank.get("value_date"),
        settlement.get("settlement_date"),
    )

    bank_reference = normalize_id(bank.get("reference"))
    candidate_utr = normalize_id(settlement.get("utr"))
    reference_exact_match = int(
        bool(bank_reference) and bool(candidate_utr) and bank_reference == candidate_utr
    )
    utr_similarity = str_similarity(bank_reference, candidate_utr)
    description_token_overlap = token_overlap(
        bank.get("description"),
        f"{settlement.get('settlement_id', '')} settlement {settlement.get('utr', '')}",
    )

    return {
        "target_id": settlement.get("settlement_id"),
        "bank_amount": bank_amount,
        "settlement_net_amount": net_amount,
        "settlement_gross_amount": gross_amount,
        "settlement_fee_amount": to_float(settlement.get("total_fees")),
        "settlement_fee_tax_amount": to_float(settlement.get("total_fee_tax")),
        "settlement_refund_amount": to_float(settlement.get("total_refunds")),
        "amount_difference": amount_difference,
        "absolute_amount_difference": absolute_amount_difference,
        "relative_amount_difference": relative_amount_difference,
        "amount_ratio": amount_ratio,
        "exact_amount_match": exact_amount_match,
        "absolute_amount_difference_vs_gross": absolute_amount_difference_vs_gross,
        "date_difference_days": date_difference_days,
        "value_date_difference_days": value_date_difference_days,
        "same_day": int(date_difference_days is not None and date_difference_days == 0),
        "within_1_day": int(date_difference_days is not None and date_difference_days <= 1),
        "within_3_days": int(date_difference_days is not None and date_difference_days <= 3),
        "within_7_days": int(date_difference_days is not None and date_difference_days <= 7),
        "reference_exact_match": reference_exact_match,
        "utr_similarity": utr_similarity,
        "description_token_overlap": description_token_overlap,
        "merchant_match": int(bank.get("merchant_id") == settlement.get("merchant_id")),
        "transaction_type_is_credit": int(bank.get("transaction_type") == "CREDIT"),
        "bank_category": bank.get("category"),
        "payment_count": settlement.get("payment_count"),
    }


def add_candidate_context(rows: list[dict]) -> list[dict]:
    """Ranks and gaps are computed on the full candidate set for this bank record."""
    if not rows:
        return []

    candidate_count = len(rows)
    amount_sorted = sorted(
        rows,
        key=lambda r: (
            r["absolute_amount_difference"]
            if r["absolute_amount_difference"] is not None
            else float("inf"),
            r.get("target_id") or "",
        ),
    )
    date_sorted = sorted(
        rows,
        key=lambda r: (
            r["date_difference_days"]
            if r["date_difference_days"] is not None
            else float("inf"),
            r.get("target_id") or "",
        ),
    )
    reference_sorted = sorted(
        rows,
        key=lambda r: (
            -(r["utr_similarity"] or 0.0),
            r.get("target_id") or "",
        ),
    )

    amount_rank = {id(row): idx + 1 for idx, row in enumerate(amount_sorted)}
    date_rank = {id(row): idx + 1 for idx, row in enumerate(date_sorted)}
    reference_rank = {id(row): idx + 1 for idx, row in enumerate(reference_sorted)}

    best_amount = amount_sorted[0]["absolute_amount_difference"] if amount_sorted else None
    second_amount = amount_sorted[1]["absolute_amount_difference"] if candidate_count > 1 else None
    best_date = date_sorted[0]["date_difference_days"] if date_sorted else None
    second_date = date_sorted[1]["date_difference_days"] if candidate_count > 1 else None
    best_reference = reference_sorted[0]["utr_similarity"] if reference_sorted else None
    second_reference = reference_sorted[1]["utr_similarity"] if candidate_count > 1 else None

    amount_gap = (
        second_amount - best_amount
        if best_amount is not None and second_amount is not None
        else None
    )
    date_gap = (
        second_date - best_date
        if best_date is not None and second_date is not None
        else None
    )
    reference_gap = (
        best_reference - second_reference
        if best_reference is not None and second_reference is not None
        else None
    )

    enriched = []
    for row in rows:
        copy = dict(row)
        copy["candidate_count"] = candidate_count
        copy["candidate_rank_by_amount"] = amount_rank[id(row)]
        copy["candidate_rank_by_date"] = date_rank[id(row)]
        copy["candidate_rank_by_reference"] = reference_rank[id(row)]
        copy["is_best_amount_candidate"] = int(amount_rank[id(row)] == 1)
        copy["is_best_date_candidate"] = int(date_rank[id(row)] == 1)
        copy["is_best_reference_candidate"] = int(reference_rank[id(row)] == 1)
        copy["best_vs_second_best_amount_gap"] = amount_gap
        copy["best_vs_second_best_date_gap"] = date_gap
        copy["best_vs_second_best_reference_gap"] = reference_gap
        enriched.append(copy)
    return enriched


def build_candidate_feature_rows(
    bank: dict,
    settlements: list[dict],
    loader: ModelLoader | None = None,
) -> list[dict]:
    schema = (loader or get_model_loader()).get_reconciliation_schema()
    required = list(schema.get("features") or [])
    base = [pair_base_features(bank, settlement) for settlement in settlements]
    with_context = add_candidate_context(base)
    aligned = []
    for row in with_context:
        payload = {key: row.get(key) for key in required}
        payload["target_id"] = row.get("target_id")
        aligned.append(payload)
    return aligned
