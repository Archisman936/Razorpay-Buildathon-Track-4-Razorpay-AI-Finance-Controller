"""Runtime verification that does not require pytest.

Run from razorpay-ai-finance-controller:

    python scripts/verify_runtime.py
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check(name: str, fn) -> bool:
    try:
        fn()
        print(f"PASS  {name}")
        return True
    except Exception as exc:
        print(f"FAIL  {name}: {exc}")
        traceback.print_exc()
        return False


def import_graph():
    import backend.app.core.config  # noqa: F401
    import backend.app.database.connection  # noqa: F401
    import backend.app.ml.model_loader  # noqa: F401
    import backend.app.ml.reconciliation_model  # noqa: F401
    import backend.app.ml.exception_classifier  # noqa: F401
    import backend.app.services.reconciliation.deterministic  # noqa: F401
    import backend.app.services.reconciliation.feature_builder  # noqa: F401
    import backend.app.services.reconciliation.ml_reconciliation  # noqa: F401
    import backend.app.services.reconciliation.exception_classification  # noqa: F401
    import backend.app.services.reconciliation.reconciliation_service  # noqa: F401
    import backend.app.services.orchestration.pipeline  # noqa: F401
    import backend.app.main  # noqa: F401
    from backend.app.services.normalization.pipeline import NormalizationPipeline

    assert NormalizationPipeline is not None


def schemas_and_joblib():
    from backend.app.ml.model_loader import ModelArtifactError, ModelLoader

    loader = ModelLoader()
    recon = loader.get_reconciliation_schema()
    exc = loader.get_exception_schema()
    assert len(recon["features"]) == 35, recon
    assert len(exc["features"]) == 19, exc
    assert recon.get("threshold") == 0.275
    status = loader.artifact_status()
    assert status["reconciliation_schema"] is True
    assert status["exception_schema"] is True
    if not status["reconciliation_model"]:
        try:
            loader.load_reconciliation_model()
            raise AssertionError("expected ModelArtifactError for missing joblib")
        except ModelArtifactError as exc:
            assert "not found" in str(exc).lower() or "best_reconciliation_model" in str(exc)
            print("  note: reconciliation .joblib is missing (expected until artifacts are copied)")
    else:
        loader.load_reconciliation_model()
        print("  note: reconciliation .joblib loaded")
    if not status["exception_model"]:
        try:
            loader.load_exception_classifier()
            raise AssertionError("expected ModelArtifactError for missing joblib")
        except ModelArtifactError as exc:
            assert "not found" in str(exc).lower() or "best_exception" in str(exc)
            print("  note: exception .joblib is missing (expected until artifacts are copied)")
    else:
        loader.load_exception_classifier()
        print("  note: exception .joblib loaded")


def postgres_config():
    from backend.app.core.config import get_settings
    from backend.app.database.connection import ping_database

    settings = get_settings()
    assert settings.db_host
    ping = ping_database(settings)
    print(f"  database ping: {ping}")


def deterministic_cases():
    from backend.app.core.constants import STATUS_MATCHED, STATUS_MATCHED_DISCREPANCY, STATUS_UNMATCHED
    from backend.app.services.reconciliation.deterministic import (
        match_order_payment,
        match_settlement_bank,
        resolve_settlement_bank,
    )

    bank = {
        "bank_record_id": "BNK_1",
        "amount": "100.00",
        "reference": "UTIB123",
        "merchant_id": "MER_1",
        "transaction_date": "2026-08-19",
    }
    settlement = {
        "settlement_id": "STL_1",
        "net_amount": "100.00",
        "utr": "UTIB123",
        "merchant_id": "MER_1",
        "settlement_date": "2026-08-19",
    }
    decision = match_settlement_bank(bank, settlement)
    assert decision.status == STATUS_MATCHED

    mismatch = dict(bank, amount="95.00")
    decision = match_settlement_bank(mismatch, settlement)
    assert decision.status == STATUS_MATCHED_DISCREPANCY
    assert decision.resolved

    unresolved = match_settlement_bank(
        dict(bank, amount="95.00", reference="AAAA"),
        dict(settlement, utr="BBBB"),
    )
    assert unresolved.status == STATUS_UNMATCHED
    assert not unresolved.resolved

    picked = resolve_settlement_bank(
        {"bank_record_id": "BNK_1", "amount": "50.00", "reference": "UTR50", "merchant_id": "MER_1", "transaction_date": "2026-08-01"},
        [
            {"settlement_id": "STL_A", "net_amount": "40.00", "utr": "OTHER", "merchant_id": "MER_1", "settlement_date": "2026-08-01"},
            {"settlement_id": "STL_B", "net_amount": "50.00", "utr": "UTR50", "merchant_id": "MER_1", "settlement_date": "2026-08-01"},
        ],
    )
    assert picked.matched_record_id == "STL_B"

    pay = match_order_payment(
        {"order_id": "ORD_1", "total_amount": "200.00", "order_date": "2026-08-01"},
        {"payment_id": "PAY_1", "order_id": "ORD_1", "amount": "180.00", "payment_date": "2026-08-01"},
    )
    assert pay.status == STATUS_MATCHED_DISCREPANCY


def feature_schema_alignment():
    from backend.app.ml.model_loader import ModelLoader
    from backend.app.services.reconciliation.feature_builder import (
        add_candidate_context,
        build_candidate_feature_rows,
        pair_base_features,
    )

    loader = ModelLoader()
    bank = {
        "bank_record_id": "BNK_1",
        "amount": "100.00",
        "reference": "ABC123",
        "merchant_id": "MER_1",
        "transaction_date": "2026-08-10",
        "value_date": "2026-08-10",
        "transaction_type": "CREDIT",
        "category": "SETTLEMENT",
        "description": "RAZORPAY SETTLEMENT STL_BEST",
    }
    close = {
        "settlement_id": "STL_BEST",
        "net_amount": "100.00",
        "gross_amount": "110.00",
        "total_fees": "8.00",
        "total_fee_tax": "1.44",
        "total_refunds": "0",
        "utr": "ABC123",
        "merchant_id": "MER_1",
        "settlement_date": "2026-08-10",
        "payment_count": 3,
    }
    far = {
        "settlement_id": "STL_FAR",
        "net_amount": "80.00",
        "gross_amount": "90.00",
        "total_fees": "5.00",
        "total_fee_tax": "0.90",
        "total_refunds": "0",
        "utr": "ZZZ999",
        "merchant_id": "MER_1",
        "settlement_date": "2026-08-20",
        "payment_count": 1,
    }
    rows = add_candidate_context([pair_base_features(bank, close), pair_base_features(bank, far)])
    by_id = {row["target_id"]: row for row in rows}
    assert by_id["STL_BEST"]["exact_amount_match"] == 1
    assert by_id["STL_BEST"]["is_best_amount_candidate"] == 1
    assert by_id["STL_FAR"]["candidate_rank_by_amount"] == 2
    assert by_id["STL_BEST"]["best_vs_second_best_amount_gap"] == 20.0
    aligned = build_candidate_feature_rows(bank, [close, far], loader)
    required = loader.get_reconciliation_schema()["features"]
    assert len(required) == 35
    for row in aligned:
        for key in required:
            assert key in row


def ml_ambiguity_routing():
    from backend.app.core.constants import STATUS_AMBIGUOUS, STATUS_ML_MATCHED, STATUS_UNMATCHED
    from backend.app.ml.model_loader import ModelLoader
    from backend.app.services.reconciliation.ml_reconciliation import MlReconciliationService

    class FakeModel:
        def __init__(self, scores):
            self._scores = scores

        def score_rows(self, feature_rows):
            return list(self._scores)

    loader = ModelLoader()
    bank = {
        "bank_record_id": "BNK_X",
        "amount": "99.00",
        "reference": "NEAR",
        "merchant_id": "MER_1",
        "transaction_date": "2026-08-10",
        "value_date": "2026-08-10",
        "transaction_type": "CREDIT",
        "category": "SETTLEMENT",
        "description": "settlement",
    }
    settlements = [
        {
            "settlement_id": "STL_TOP",
            "net_amount": "100.00",
            "gross_amount": "110.00",
            "total_fees": "8",
            "total_fee_tax": "1",
            "total_refunds": "0",
            "utr": "NEAR",
            "merchant_id": "MER_1",
            "settlement_date": "2026-08-10",
            "payment_count": 2,
        },
        {
            "settlement_id": "STL_SECOND",
            "net_amount": "98.00",
            "gross_amount": "108.00",
            "total_fees": "8",
            "total_fee_tax": "1",
            "total_refunds": "0",
            "utr": "NEARX",
            "merchant_id": "MER_1",
            "settlement_date": "2026-08-11",
            "payment_count": 2,
        },
    ]
    clear = MlReconciliationService(loader=loader, model=FakeModel([0.91, 0.20])).score_candidates(bank, settlements)
    assert clear.status == STATUS_ML_MATCHED
    assert clear.matched_record_id == "STL_TOP"
    amb = MlReconciliationService(loader=loader, model=FakeModel([0.40, 0.38])).score_candidates(bank, settlements)
    assert amb.status == STATUS_AMBIGUOUS
    low = MlReconciliationService(loader=loader, model=FakeModel([0.10, 0.05])).score_candidates(bank, settlements)
    assert low.status == STATUS_UNMATCHED


def exception_features():
    from backend.app.ml.model_loader import ModelLoader
    from backend.app.services.reconciliation.exception_classification import (
        ExceptionClassificationService,
        build_exception_features,
        features_from_bank_settlement,
    )

    loader = ModelLoader()
    row = build_exception_features(
        entity_type="bank_record",
        affected_field="amount",
        observed_value="95.00",
        expected_value="100.00",
        entity_amount="95.00",
        fee_amount="2.00",
        tax_amount="0.36",
        refund_amount="0",
        adjustment_amount="5.00",
        loader=loader,
    )
    schema = loader.get_exception_schema()
    assert set(row) == set(schema["features"])
    assert row["entity_type"] == "BNK"
    bank = {
        "bank_record_id": "BNK_1",
        "amount": "90",
        "reference": "UTR1",
        "transaction_date": "2026-08-01",
        "description": "x",
    }
    settlement = {
        "settlement_id": "STL_1",
        "net_amount": "100",
        "utr": "UTR1",
        "settlement_date": "2026-08-01",
        "total_fees": "1",
        "total_fee_tax": "0.18",
        "total_refunds": "0",
        "total_adjustments": "0",
    }
    routed = features_from_bank_settlement(bank, settlement, loader)
    assert routed["affected_field"] == "amount"

    class FakeClassifier:
        def predict(self, feature_row):
            return {"exception_type": "AMOUNT_DISCREPANCY", "confidence": 0.88, "probabilities": {}}

    result = ExceptionClassificationService(loader=loader, classifier=FakeClassifier()).classify(row)
    assert result["exception_type"] == "AMOUNT_DISCREPANCY"


def structured_output():
    from backend.app.core.constants import METHOD_DETERMINISTIC, STATUS_MATCHED, STATUS_UNMATCHED
    from backend.app.ml.model_loader import ModelLoader
    from backend.app.services.reconciliation.reconciliation_service import ReconciliationService

    class BankRepo:
        def __init__(self, row):
            self.row = row

        def get_by_id(self, bank_record_id):
            return self.row if self.row.get("bank_record_id") == bank_record_id else None

    class SettlementRepo:
        def __init__(self, rows):
            self.rows = rows

        def get_by_id(self, settlement_id):
            return next((row for row in self.rows if row["settlement_id"] == settlement_id), None)

        def list_for_merchant_window(self, merchant_id, center_date, window_days, limit=50):
            return [row for row in self.rows if row["merchant_id"] == merchant_id][:limit]

        def list_by_merchant(self, merchant_id, limit=200):
            return [row for row in self.rows if row["merchant_id"] == merchant_id][:limit]

    loader = ModelLoader()
    bank = {
        "bank_record_id": "BNK_1",
        "amount": "250.00",
        "reference": "UTR250",
        "merchant_id": "MER_1",
        "transaction_date": "2026-08-02",
        "value_date": "2026-08-02",
        "transaction_type": "CREDIT",
        "category": "SETTLEMENT",
        "description": "ok",
    }
    stl = {
        "settlement_id": "STL_1",
        "net_amount": "250.00",
        "gross_amount": "260.00",
        "total_fees": "8",
        "total_fee_tax": "2",
        "total_refunds": "0",
        "total_adjustments": "0",
        "utr": "UTR250",
        "merchant_id": "MER_1",
        "settlement_date": "2026-08-02",
        "payment_count": 1,
    }
    service = ReconciliationService(
        loader=loader,
        bank_repo=BankRepo(bank),
        settlement_repo=SettlementRepo([stl]),
    )
    result = service.run("bank_record", "BNK_1", include_ml=False, include_exception=False)
    assert result["status"] == STATUS_MATCHED
    assert result["reconciliation_method"] == METHOD_DETERMINISTIC
    assert result["matched_record_id"] == "STL_1"
    assert result["case_id"]
    assert result["reason_codes"]
    assert result["explanation_facts"]

    unresolved_bank = dict(bank, bank_record_id="BNK_2", amount="10.00", reference="NOPE")
    far = dict(stl, settlement_id="STL_9", net_amount="99.00", utr="OTHER")
    service2 = ReconciliationService(
        loader=loader,
        bank_repo=BankRepo(unresolved_bank),
        settlement_repo=SettlementRepo([far]),
    )
    result2 = service2.run("bank_record", "BNK_2", include_ml=False, include_exception=False)
    assert result2["status"] == STATUS_UNMATCHED
    assert result2["candidate_records"]


def normalization_untouched():
    from decimal import Decimal

    from backend.app.services.normalization.pipeline import NormalizationPipeline
    from backend.app.services.normalization.transforms.amounts import amounts_approximately_equal

    pipeline = NormalizationPipeline()
    record = pipeline.normalize_record(
        {
            "bank_record_id": "BNK_000001",
            "merchant_id": "MER_000001",
            "amount": "10.50",
            "currency": "inr",
            "transaction_type": "credit",
            "transaction_date": "2026-08-01",
        },
        entity_type="bank",
        source="TEST",
        source_file_id="t.jsonl",
        row_number=1,
    )
    assert record["currency"] == "INR"
    assert record["transaction_type"] == "CREDIT"
    assert "_lineage" in record
    assert amounts_approximately_equal(Decimal("100.00"), Decimal("100.50"), Decimal("0.02"), Decimal("1"))


def health_endpoint():
    from fastapi.testclient import TestClient

    from backend.app.main import create_app

    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["models"]["reconciliation_schema"] is True
    assert body["models"]["exception_schema"] is True


def main() -> int:
    checks = [
        ("import_graph", import_graph),
        ("schemas_and_joblib", schemas_and_joblib),
        ("postgres_config", postgres_config),
        ("deterministic_cases", deterministic_cases),
        ("feature_schema_alignment", feature_schema_alignment),
        ("ml_ambiguity_routing", ml_ambiguity_routing),
        ("exception_features", exception_features),
        ("structured_output", structured_output),
        ("normalization_untouched", normalization_untouched),
        ("health_endpoint", health_endpoint),
    ]
    passed = 0
    for name, fn in checks:
        if check(name, fn):
            passed += 1
    print(f"\n{passed}/{len(checks)} checks passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
