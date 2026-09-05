"""Real ML artifact inference tests - actually load and run trained .joblib files."""
from __future__ import annotations
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
RECON_DIR = ROOT / "tools" / "ML_Models" / "Reconciliation Model"
EXC_DIR = ROOT / "tools" / "ML_Models" / "Exception Classification"

def _load_schema(path):
    import json
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)

def _load_model(path):
    import joblib
    return joblib.load(path)

def _build_recon_row(features):
    d = {
        "bank_amount": 5000.0, "settlement_net_amount": 4997.5, "settlement_gross_amount": 5200.0,
        "settlement_fee_amount": 156.0, "settlement_fee_tax_amount": 28.08, "settlement_refund_amount": 0.0,
        "amount_difference": 2.5, "absolute_amount_difference": 2.5, "relative_amount_difference": 0.0005,
        "amount_ratio": 1.0005, "exact_amount_match": 0, "absolute_amount_difference_vs_gross": 200.0,
        "date_difference_days": 1, "value_date_difference_days": 1, "same_day": 0,
        "within_1_day": 1, "within_3_days": 1, "within_7_days": 1,
        "reference_exact_match": 0, "utr_similarity": 0.91, "description_token_overlap": 0.15,
        "merchant_match": 1, "transaction_type_is_credit": 1, "bank_category": 1, "payment_count": 3,
        "candidate_count": 4, "candidate_rank_by_amount": 1, "candidate_rank_by_date": 2,
        "candidate_rank_by_reference": 1, "is_best_amount_candidate": 1, "is_best_date_candidate": 0,
        "is_best_reference_candidate": 1, "best_vs_second_best_amount_gap": 5.0,
        "best_vs_second_best_date_gap": 1.0, "best_vs_second_best_reference_gap": 0.07,
    }
    return {col: d.get(col, 0) for col in features}

def _build_exc_row(features):
    d = {
        "entity_type": "BNK", "affected_field": "amount", "value_pair_present": 1,
        "value_exact_match": 0, "value_normalized_id_match": 0, "value_str_similarity": 0.6,
        "value_token_overlap": 0.3, "value_numeric_diff": 2.5, "value_numeric_abs_diff": 2.5,
        "value_numeric_rel_diff": 0.0005, "value_is_numeric_pair": 1, "value_date_diff_days": None,
        "value_is_date_pair": 0, "entity_amount": 5000.0, "fee_amount_context": 156.0,
        "tax_amount_context": 28.08, "refund_amount_context": 0.0,
        "adjustment_amount_context": None, "diff_to_adjustment_ratio": None,
    }
    return {col: d.get(col) for col in features}


class TestReconciliationModelInference:
    def test_schema_35_features(self):
        schema = _load_schema(RECON_DIR / "feature_schema.json")
        assert len(schema["features"]) == 35

    def test_schema_threshold(self):
        schema = _load_schema(RECON_DIR / "feature_schema.json")
        assert 0.0 < float(schema["threshold"]) < 1.0

    def test_joblib_is_estimator(self):
        raw = _load_model(RECON_DIR / "best_reconciliation_model.joblib")
        m = raw["model"] if isinstance(raw, dict) else raw
        assert hasattr(m, "predict") or hasattr(m, "predict_proba")

    def test_inference_one_row(self):
        import pandas as pd
        from backend.app.ml.model_loader import unwrap_estimator
        schema = _load_schema(RECON_DIR / "feature_schema.json")
        features = schema["features"]
        estimator, _ = unwrap_estimator(_load_model(RECON_DIR / "best_reconciliation_model.joblib"), "recon")
        frame = pd.DataFrame([_build_recon_row(features)])[features]
        if hasattr(estimator, "predict_proba"):
            proba = estimator.predict_proba(frame)
            assert proba.shape == (1, 2)
            assert abs(proba[0].sum() - 1.0) < 1e-6
        else:
            assert len(estimator.predict(frame)) == 1

    def test_inference_four_candidates(self):
        import pandas as pd
        from backend.app.ml.model_loader import unwrap_estimator
        schema = _load_schema(RECON_DIR / "feature_schema.json")
        features = schema["features"]
        estimator, _ = unwrap_estimator(_load_model(RECON_DIR / "best_reconciliation_model.joblib"), "recon")
        rows = [{**_build_recon_row(features), "candidate_rank_by_amount": i+1, "absolute_amount_difference": float(i)*10} for i in range(4)]
        frame = pd.DataFrame(rows)[features]
        n = estimator.predict_proba(frame).shape[0] if hasattr(estimator, "predict_proba") else len(estimator.predict(frame))
        assert n == 4

    def test_model_loader_and_score_rows(self):
        from backend.app.ml.model_loader import ModelLoader
        from backend.app.ml.reconciliation_model import ReconciliationModel
        loader = ModelLoader()
        loaded = loader.load_reconciliation_model()
        assert loaded.name == "reconciliation" and len(loaded.features) == 35
        scores = ReconciliationModel(loaded).score_rows([_build_recon_row(loaded.features)])
        assert len(scores) == 1 and isinstance(scores[0], float) and 0.0 <= scores[0] <= 1.0


class TestExceptionClassifierInference:
    def test_schema_7_classes(self):
        schema = _load_schema(EXC_DIR / "feature_schema.json")
        assert set(schema["classes"]) == {"AMOUNT_DISCREPANCY","DESCRIPTION_MISMATCH","DUPLICATE","FORMAT_MISMATCH","MISSING_RECORD","TIMING_DIFFERENCE","WRONG_REFERENCE"}

    def test_schema_19_features(self):
        assert len(_load_schema(EXC_DIR / "feature_schema.json")["features"]) == 19

    def test_joblib_is_estimator(self):
        raw = _load_model(EXC_DIR / "best_exception_classifier.joblib")
        m = raw["model"] if isinstance(raw, dict) else raw
        assert hasattr(m, "predict")

    def test_inference_known_class(self):
        import pandas as pd
        from backend.app.ml.model_loader import unwrap_estimator
        schema = _load_schema(EXC_DIR / "feature_schema.json")
        features = schema["features"]
        estimator, _ = unwrap_estimator(_load_model(EXC_DIR / "best_exception_classifier.joblib"), "exc")
        pred = str(estimator.predict(pd.DataFrame([_build_exc_row(features)])[features])[0])
        known = {"AMOUNT_DISCREPANCY","DESCRIPTION_MISMATCH","DUPLICATE","FORMAT_MISMATCH","MISSING_RECORD","TIMING_DIFFERENCE","WRONG_REFERENCE"} | {str(i) for i in range(7)}
        assert pred in known, f"Unknown class: {pred!r}"

    def test_inference_proba_7_classes(self):
        import pandas as pd
        from backend.app.ml.model_loader import unwrap_estimator
        schema = _load_schema(EXC_DIR / "feature_schema.json")
        features = schema["features"]
        estimator, _ = unwrap_estimator(_load_model(EXC_DIR / "best_exception_classifier.joblib"), "exc")
        if not hasattr(estimator, "predict_proba"):
            pytest.skip("No predict_proba")
        proba = estimator.predict_proba(pd.DataFrame([_build_exc_row(features)])[features])
        assert proba.shape == (1, 7) and abs(proba[0].sum() - 1.0) < 1e-6

    def test_exception_classifier_integration(self):
        from backend.app.ml.exception_classifier import ExceptionClassifier
        from backend.app.ml.model_loader import ModelLoader
        result = ExceptionClassifier.from_loader(ModelLoader()).predict(
            _build_exc_row(_load_schema(EXC_DIR / "feature_schema.json")["features"])
        )
        assert result["exception_type"] is not None
        if result["confidence"] is not None:
            assert 0.0 <= result["confidence"] <= 1.0
