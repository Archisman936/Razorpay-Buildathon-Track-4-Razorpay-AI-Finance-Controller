"""Build exception-classifier features and run inference when appropriate."""

from __future__ import annotations

from backend.app.core.constants import ENTITY_TYPE_CODES
from backend.app.ml.exception_classifier import ExceptionClassifier
from backend.app.ml.model_loader import ModelLoader, get_model_loader
from backend.app.services.reconciliation.metrics import (
    days_between,
    normalize_id,
    str_similarity,
    to_float,
    token_overlap,
)


def entity_type_code(entity_type: str) -> str:
    if not entity_type:
        return "UNK"
    key = entity_type.strip().lower()
    if key in ENTITY_TYPE_CODES:
        return ENTITY_TYPE_CODES[key]
    return entity_type.strip().upper()[:3]


def infer_affected_field(
    observed,
    expected,
    numeric_diff: float | None,
    date_diff: int | None,
    default_field: str,
) -> str:
    if date_diff not in (None, 0) and (numeric_diff in (None, 0.0)):
        return default_field if "date" in default_field else "transaction_date"
    if numeric_diff not in (None, 0.0):
        return default_field if default_field in {
            "amount",
            "net_amount",
            "total_amount",
            "reference",
        } else "amount"
    obs_id = normalize_id(observed)
    exp_id = normalize_id(expected)
    if obs_id and exp_id and obs_id == exp_id and str(observed) != str(expected):
        return default_field if "id" in default_field or default_field in {
            "reference",
            "utr",
        } else "reference"
    if observed and expected and str(observed) != str(expected):
        return default_field
    return default_field


def build_exception_features(
    *,
    entity_type: str,
    affected_field: str,
    observed_value,
    expected_value,
    entity_amount=None,
    fee_amount=None,
    tax_amount=None,
    refund_amount=None,
    adjustment_amount=None,
    loader: ModelLoader | None = None,
) -> dict:
    schema = (loader or get_model_loader()).get_exception_schema()
    required = list(schema.get("features") or [])

    obs_s = "" if observed_value is None else str(observed_value)
    exp_s = "" if expected_value is None else str(expected_value)
    pair_present = int(bool(obs_s) and bool(exp_s))
    exact_match = int(pair_present and obs_s == exp_s)
    normalized_id_match = int(
        pair_present and normalize_id(obs_s) == normalize_id(exp_s) and bool(normalize_id(obs_s))
    )
    similarity = str_similarity(obs_s, exp_s) if pair_present else 0.0
    overlap = token_overlap(obs_s, exp_s) if pair_present else 0.0

    obs_n = to_float(observed_value)
    exp_n = to_float(expected_value)
    is_numeric = int(obs_n is not None and exp_n is not None)
    numeric_diff = (obs_n - exp_n) if is_numeric else None
    numeric_abs = abs(numeric_diff) if numeric_diff is not None else None
    numeric_rel = (
        numeric_abs / abs(exp_n)
        if numeric_abs is not None and exp_n not in (None, 0)
        else None
    )

    date_diff = days_between(observed_value, expected_value)
    is_date = int(date_diff is not None)

    amount = to_float(entity_amount)
    fee = to_float(fee_amount)
    tax = to_float(tax_amount)
    refund = to_float(refund_amount)
    adjustment = to_float(adjustment_amount)
    diff_to_adj = None
    if numeric_abs is not None and adjustment not in (None, 0):
        diff_to_adj = numeric_abs / abs(adjustment)

    row = {
        "entity_type": entity_type_code(entity_type),
        "affected_field": affected_field,
        "value_pair_present": pair_present,
        "value_exact_match": exact_match,
        "value_normalized_id_match": normalized_id_match,
        "value_str_similarity": similarity,
        "value_token_overlap": overlap,
        "value_numeric_diff": numeric_diff,
        "value_numeric_abs_diff": numeric_abs,
        "value_numeric_rel_diff": numeric_rel,
        "value_is_numeric_pair": is_numeric,
        "value_date_diff_days": date_diff,
        "value_is_date_pair": is_date,
        "entity_amount": amount,
        "fee_amount_context": fee,
        "tax_amount_context": tax,
        "refund_amount_context": refund,
        "adjustment_amount_context": adjustment,
        "diff_to_adjustment_ratio": diff_to_adj,
    }
    return {key: row.get(key) for key in required}


def features_from_bank_settlement(
    bank: dict,
    settlement: dict | None,
    loader: ModelLoader | None = None,
) -> dict:
    if settlement is None:
        return build_exception_features(
            entity_type="bank_record",
            affected_field="settlement_id",
            observed_value=bank.get("bank_record_id"),
            expected_value=None,
            entity_amount=bank.get("amount"),
            loader=loader,
        )

    amount_obs = bank.get("amount")
    amount_exp = settlement.get("net_amount")
    ref_obs = bank.get("reference")
    ref_exp = settlement.get("utr")
    date_obs = bank.get("transaction_date")
    date_exp = settlement.get("settlement_date")

    amount_abs = None
    a = to_float(amount_obs)
    b = to_float(amount_exp)
    if a is not None and b is not None:
        amount_abs = abs(a - b)
    date_diff = days_between(date_obs, date_exp)
    ref_exact = normalize_id(ref_obs) == normalize_id(ref_exp) and bool(normalize_id(ref_obs))

    if amount_abs is not None and amount_abs >= 0.01:
        field, observed, expected = "amount", amount_obs, amount_exp
    elif date_diff not in (None, 0):
        field, observed, expected = "transaction_date", date_obs, date_exp
    elif not ref_exact:
        field, observed, expected = "reference", ref_obs, ref_exp
    else:
        field, observed, expected = "description", bank.get("description"), settlement.get("settlement_id")

    return build_exception_features(
        entity_type="bank_record",
        affected_field=field,
        observed_value=observed,
        expected_value=expected,
        entity_amount=bank.get("amount"),
        fee_amount=settlement.get("total_fees"),
        tax_amount=settlement.get("total_fee_tax"),
        refund_amount=settlement.get("total_refunds"),
        adjustment_amount=settlement.get("total_adjustments"),
        loader=loader,
    )


class ExceptionClassificationService:
    def __init__(
        self,
        loader: ModelLoader | None = None,
        classifier: ExceptionClassifier | None = None,
    ) -> None:
        self.loader = loader or get_model_loader()
        self.classifier = classifier

    def classify(self, feature_row: dict) -> dict:
        if self.classifier is None:
            self.classifier = ExceptionClassifier.from_loader(self.loader)
        return self.classifier.predict(feature_row)
