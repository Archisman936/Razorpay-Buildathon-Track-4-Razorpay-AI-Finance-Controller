"""Build settlement candidates for a bank record without using ground truth."""

from __future__ import annotations

from backend.app.core.config import Settings, get_settings
from backend.app.services.reconciliation.metrics import (
    days_between,
    normalize_id,
    str_similarity,
    to_float,
)


def generate_settlement_candidates(
    bank: dict,
    settlements: list[dict],
    settings: Settings | None = None,
) -> list[dict]:
    settings = settings or get_settings()
    window = settings.candidate_window_days
    cap = settings.max_candidates
    scored: list[tuple[float, dict]] = []

    for settlement in settlements:
        if settlement.get("merchant_id") != bank.get("merchant_id"):
            continue
        date_diff = days_between(
            bank.get("transaction_date"),
            settlement.get("settlement_date"),
        )
        if date_diff is not None and date_diff > window:
            continue
        amount_gap = _abs_diff(bank.get("amount"), settlement.get("net_amount"))
        ref_sim = str_similarity(
            normalize_id(bank.get("reference")),
            normalize_id(settlement.get("utr")),
        )
        closeness = 0.0
        if amount_gap is not None:
            closeness += 1.0 / (1.0 + amount_gap)
        closeness += ref_sim
        if date_diff is not None:
            closeness += 1.0 / (1.0 + date_diff)
        scored.append((closeness, settlement))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:cap]]


def _abs_diff(left, right) -> float | None:
    a = to_float(left)
    b = to_float(right)
    if a is None or b is None:
        return None
    return abs(a - b)
