"""API integration tests using FastAPI TestClient with mocked repositories.

Tests cover:
  - GET /health: schema files present, DB status reported
  - GET /api/v1/health: alias route
  - POST /api/v1/reconciliation/run: deterministic match
  - POST /api/v1/reconciliation/run: ML-required ambiguous case (actual model)
  - POST /api/v1/reconciliation/run: exception classification triggered
  - POST /api/v1/reconciliation/run: unknown source_type -> 400
  - POST /api/v1/reconciliation/run: missing record -> 404

Repositories are mocked so no PostgreSQL instance is required.
ML models are NOT mocked -- they use the real .joblib artifacts.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.main import create_app
from backend.app.ml.model_loader import get_model_loader
from backend.app.services.orchestration.pipeline import ReconciliationPipeline
from backend.app.services.reconciliation.reconciliation_service import ReconciliationService


# ---------------------------------------------------------------------------
# Shared mock repos
# ---------------------------------------------------------------------------

class MockBankRepo:
    def __init__(self, rows=()):
        self._rows = {r["bank_record_id"]: r for r in rows}
    def get_by_id(self, bank_record_id):
        return self._rows.get(bank_record_id)
    def list_by_merchant(self, merchant_id, limit=200):
        return [r for r in self._rows.values() if r.get("merchant_id") == merchant_id][:limit]


class MockSettlementRepo:
    def __init__(self, rows=()):
        self._rows = rows
    def get_by_id(self, settlement_id):
        return next((r for r in self._rows if r["settlement_id"] == settlement_id), None)
    def get_by_utr(self, utr):
        return next((r for r in self._rows if r.get("utr") == utr), None)
    def list_for_merchant_window(self, merchant_id, center_date, window_days, limit=50):
        return [r for r in self._rows if r.get("merchant_id") == merchant_id][:limit]
    def list_by_merchant(self, merchant_id, limit=200):
        return [r for r in self._rows if r.get("merchant_id") == merchant_id][:limit]


class MockPaymentRepo:
    def get_by_id(self, payment_id): return None
    def get_order(self, order_id): return None
    def list_by_order(self, order_id): return []
    def list_fees(self, payment_id): return []
    def list_refunds(self, payment_id): return []
    def list_settlement_links(self, payment_id): return []


class MockEntityRepo:
    def get_invoice(self, invoice_id): return None
    def list_invoices_for_order(self, order_id): return []
    def list_gst_for_invoice(self, invoice_id): return []
    def list_adjustments_for_settlement(self, settlement_id): return []
    def list_books_for_reference(self, reference_id): return []


# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

_BANK_DETERMINISTIC = {
    "bank_record_id": "BNK_DET_001",
    "amount": "1500.00",
    "reference": "UTR1500EXACT",
    "merchant_id": "MER_001",
    "transaction_date": "2026-08-15",
    "value_date": "2026-08-15",
    "transaction_type": "CREDIT",
    "category": "SETTLEMENT",
    "description": "NEFT CREDIT",
}

_STL_DETERMINISTIC = {
    "settlement_id": "STL_DET_001",
    "net_amount": "1500.00",
    "gross_amount": "1560.00",
    "total_fees": "50.0",
    "total_fee_tax": "9.0",
    "total_refunds": "0.0",
    "total_adjustments": "0.0",
    "utr": "UTR1500EXACT",
    "merchant_id": "MER_001",
    "settlement_date": "2026-08-15",
    "payment_count": 2,
}

_BANK_AMBIGUOUS = {
    "bank_record_id": "BNK_AMB_001",
    "amount": "3200.00",
    "reference": "AMBIGUOUSREF01",
    "merchant_id": "MER_001",
    "transaction_date": "2026-08-20",
    "value_date": "2026-08-20",
    "transaction_type": "CREDIT",
    "category": "SETTLEMENT",
    "description": "BANK TRANSFER CREDIT",
}

def _ambiguous_settlements():
    base = {
        "gross_amount": "3300.00", "total_fees": "80.0", "total_fee_tax": "14.4",
        "total_refunds": "0.0", "total_adjustments": "0.0",
        "merchant_id": "MER_001", "payment_count": 3,
    }
    return [
        {**base, "settlement_id": "STL_AMB_001", "net_amount": "3205.60", "utr": "AMBIGUOUSREF01X", "settlement_date": "2026-08-19"},
        {**base, "settlement_id": "STL_AMB_002", "net_amount": "3198.00", "utr": "AMBIGUOUSREF02X", "settlement_date": "2026-08-21"},
        {**base, "settlement_id": "STL_AMB_003", "net_amount": "3210.00", "utr": "AMBIGUOUSREF03X", "settlement_date": "2026-08-22"},
    ]


# ---------------------------------------------------------------------------
# App factory with mocked repos
# ---------------------------------------------------------------------------

def _make_client(bank_rows=(), settlement_rows=()):
    settings = get_settings()
    loader = get_model_loader()
    service = ReconciliationService(
        settings=settings,
        loader=loader,
        bank_repo=MockBankRepo(bank_rows),
        settlement_repo=MockSettlementRepo(settlement_rows),
        payment_repo=MockPaymentRepo(),
        entity_repo=MockEntityRepo(),
    )
    pipeline = ReconciliationPipeline(service=service)

    from backend.app.api.routes import api_router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(api_router)

    # Override get_pipeline dependency
    from backend.app.api.dependencies import get_pipeline
    app.dependency_overrides[get_pipeline] = lambda: pipeline

    return TestClient(app)


# ---------------------------------------------------------------------------
# Health tests
# ---------------------------------------------------------------------------

def test_health_returns_200_with_model_schemas():
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["models"]["reconciliation_schema"] is True
    assert body["models"]["exception_schema"] is True


def test_api_v1_health_alias():
    client = TestClient(create_app())
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] in {"ok", "degraded"}


# ---------------------------------------------------------------------------
# Test Case A -- deterministic match
# ---------------------------------------------------------------------------

def test_deterministic_match_bank():
    """Exact UTR + exact amount -> STATUS_MATCHED_EXACT via deterministic rule. No ML needed."""
    client = _make_client(
        bank_rows=[_BANK_DETERMINISTIC],
        settlement_rows=[_STL_DETERMINISTIC],
    )
    resp = client.post("/api/v1/reconciliation/run", json={
        "source_type": "bank_record",
        "source_id": "BNK_DET_001",
        "include_ml": False,
        "include_exception": False,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "MATCHED_EXACT"
    assert body["reconciliation_method"] == "deterministic"
    assert body["matched_record_id"] == "STL_DET_001"
    assert body["source_record_id"] == "BNK_DET_001"
    assert body["match_probability"] is None
    assert "EXACT_AMOUNT" in body["reason_codes"] or "EXACT_UTR" in body["reason_codes"]
    assert "case_id" in body


# ---------------------------------------------------------------------------
# Test Case B -- ML reconciliation (actual model)
# ---------------------------------------------------------------------------

def test_ml_reconciliation_ambiguous_case():
    """Ambiguous case: deterministic fails, real model is invoked, candidates ranked."""
    client = _make_client(
        bank_rows=[_BANK_AMBIGUOUS],
        settlement_rows=_ambiguous_settlements(),
    )
    resp = client.post("/api/v1/reconciliation/run", json={
        "source_type": "bank_record",
        "source_id": "BNK_AMB_001",
        "include_ml": True,
        "include_exception": False,
    })
    assert resp.status_code == 200
    body = resp.json()
    # ML was involved
    assert body["reconciliation_method"] in {"ml", "ambiguous", "unmatched"}
    assert body["source_record_id"] == "BNK_AMB_001"
    # Candidates must be returned
    assert isinstance(body["candidate_records"], list)
    assert len(body["candidate_records"]) > 0
    # If ML matched, probability must be present
    if body["reconciliation_method"] == "ml":
        assert body["match_probability"] is not None
        assert 0.0 <= body["match_probability"] <= 1.0
        assert body["matched_record_id"] is not None


# ---------------------------------------------------------------------------
# Test Case C -- exception classification (actual classifier)
# ---------------------------------------------------------------------------

def test_exception_classification_on_unmatched():
    """Unmatched bank record triggers exception classifier with real .joblib."""
    bank_no_match = {
        **_BANK_AMBIGUOUS,
        "bank_record_id": "BNK_EXC_001",
        "amount": "9999.00",
        "reference": "TOTALLYWRONGREF",
    }
    client = _make_client(
        bank_rows=[bank_no_match],
        settlement_rows=[],  # no settlements -> unmatched
    )
    resp = client.post("/api/v1/reconciliation/run", json={
        "source_type": "bank_record",
        "source_id": "BNK_EXC_001",
        "include_ml": False,
        "include_exception": True,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "UNMATCHED"
    # Exception classifier must have run
    assert body["exception_type"] is not None
    known_classes = {
        "AMOUNT_DISCREPANCY", "DESCRIPTION_MISMATCH", "DUPLICATE",
        "FORMAT_MISMATCH", "MISSING_RECORD", "TIMING_DIFFERENCE", "WRONG_REFERENCE",
    }
    assert body["exception_type"] in known_classes, f"Unknown: {body['exception_type']!r}"
    # Confidence should be present (classifier supports predict_proba)
    if body.get("exception_confidence") is not None:
        assert 0.0 <= body["exception_confidence"] <= 1.0


# ---------------------------------------------------------------------------
# Invalid inputs
# ---------------------------------------------------------------------------

def test_unknown_source_type_returns_400():
    client = _make_client()
    resp = client.post("/api/v1/reconciliation/run", json={
        "source_type": "widget",
        "source_id": "W_001",
        "include_ml": False,
        "include_exception": False,
    })
    assert resp.status_code == 400


def test_missing_record_returns_404():
    client = _make_client(bank_rows=[], settlement_rows=[])
    resp = client.post("/api/v1/reconciliation/run", json={
        "source_type": "bank_record",
        "source_id": "BNK_DOES_NOT_EXIST",
        "include_ml": False,
        "include_exception": False,
    })
    assert resp.status_code == 404


def test_malformed_request_returns_422():
    client = _make_client()
    resp = client.post("/api/v1/reconciliation/run", json={"source_type": "bank_record"})
    assert resp.status_code == 422
