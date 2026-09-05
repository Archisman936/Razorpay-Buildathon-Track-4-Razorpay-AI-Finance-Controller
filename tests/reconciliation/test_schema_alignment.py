"""Feature schema alignment tests.

Verifies that the backend feature builders produce exactly the column names
required by the trained model schemas. No extra columns, no missing columns.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECON_SCHEMA = ROOT / "tools" / "ML_Models" / "Reconciliation Model" / "feature_schema.json"
EXC_SCHEMA = ROOT / "tools" / "ML_Models" / "Exception Classification" / "feature_schema.json"


def _load_schema(path):
    import json
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _make_bank_and_settlement():
    bank = {
        "bank_record_id": "BNK_ALIGN_001",
        "amount": "2500.00",
        "reference": "UTRTEST001",
        "merchant_id": "MER_ALIGN",
        "transaction_date": "2026-08-10",
        "value_date": "2026-08-10",
        "transaction_type": "CREDIT",
        "category": "SETTLEMENT",
        "description": "NEFT CREDIT settlement",
    }
    settlements = [
        {
            "settlement_id": "STL_ALIGN_001",
            "net_amount": "2495.00",
            "gross_amount": "2600.00",
            "total_fees": "90.0",
            "total_fee_tax": "16.2",
            "total_refunds": "0.0",
            "total_adjustments": "0.0",
            "utr": "UTRTEST001",
            "merchant_id": "MER_ALIGN",
            "settlement_date": "2026-08-10",
            "payment_count": 2,
        },
        {
            "settlement_id": "STL_ALIGN_002",
            "net_amount": "2490.00",
            "gross_amount": "2600.00",
            "total_fees": "92.0",
            "total_fee_tax": "16.56",
            "total_refunds": "0.0",
            "total_adjustments": "0.0",
            "utr": "UTRTEST002",
            "merchant_id": "MER_ALIGN",
            "settlement_date": "2026-08-12",
            "payment_count": 2,
        },
    ]
    return bank, settlements


# ---------------------------------------------------------------------------
# Reconciliation feature schema alignment
# ---------------------------------------------------------------------------

def test_recon_feature_names_match_schema_exactly(schema_loader):
    """build_candidate_feature_rows must produce exactly the 35 schema columns."""
    from backend.app.services.reconciliation.feature_builder import build_candidate_feature_rows

    schema = _load_schema(RECON_SCHEMA)
    required = set(schema["features"])

    bank, settlements = _make_bank_and_settlement()
    rows = build_candidate_feature_rows(bank, settlements, schema_loader)

    assert len(rows) == 2
    for row in rows:
        produced = set(row.keys()) - {"target_id"}  # target_id is traceability, not a feature
        missing = required - produced
        extra = produced - required
        assert not missing, f"Missing features: {sorted(missing)}"
        assert not extra, f"Unexpected extra features: {sorted(extra)}"


def test_recon_feature_count_per_row(schema_loader):
    from backend.app.services.reconciliation.feature_builder import build_candidate_feature_rows
    schema = _load_schema(RECON_SCHEMA)
    bank, settlements = _make_bank_and_settlement()
    rows = build_candidate_feature_rows(bank, settlements, schema_loader)
    for row in rows:
        feature_keys = [k for k in row if k != "target_id"]
        assert len(feature_keys) == 35, f"Expected 35, got {len(feature_keys)}"


def test_candidate_context_features_are_populated(schema_loader):
    """Rank and gap features must have non-None values for multi-candidate sets."""
    from backend.app.services.reconciliation.feature_builder import build_candidate_feature_rows
    bank, settlements = _make_bank_and_settlement()
    rows = build_candidate_feature_rows(bank, settlements, schema_loader)
    for row in rows:
        assert row["candidate_count"] == 2
        assert row["candidate_rank_by_amount"] in {1, 2}
        assert row["candidate_rank_by_date"] in {1, 2}
        assert row["candidate_rank_by_reference"] in {1, 2}
        assert row["is_best_amount_candidate"] in {0, 1}
        assert row["is_best_date_candidate"] in {0, 1}
        assert row["is_best_reference_candidate"] in {0, 1}
        # Gaps must be non-None when there are 2+ candidates
        assert row["best_vs_second_best_amount_gap"] is not None
        assert row["best_vs_second_best_date_gap"] is not None
        assert row["best_vs_second_best_reference_gap"] is not None


def test_same_day_none_guard(schema_loader):
    """same_day must be 0 (not True) when transaction_date is missing."""
    from backend.app.services.reconciliation.feature_builder import pair_base_features
    bank_no_date = {
        "bank_record_id": "BNK_NODATE",
        "amount": "100.00",
        "reference": "REF",
        "merchant_id": "MER_1",
        "transaction_date": None,  # no date
        "value_date": None,
        "transaction_type": "CREDIT",
        "category": "SETTLEMENT",
        "description": "x",
    }
    settlement = {
        "settlement_id": "STL_1",
        "net_amount": "100.00",
        "gross_amount": "105.00",
        "total_fees": "5.0",
        "total_fee_tax": "0.9",
        "total_refunds": "0.0",
        "utr": "REF",
        "merchant_id": "MER_1",
        "settlement_date": "2026-08-10",
        "payment_count": 1,
    }
    features = pair_base_features(bank_no_date, settlement)
    # date_difference_days is None when date is missing
    assert features["date_difference_days"] is None
    # same_day must NOT be True when date is None
    assert features["same_day"] == 0
    # within_N_day flags must also be 0
    assert features["within_1_day"] == 0
    assert features["within_3_days"] == 0
    assert features["within_7_days"] == 0


# ---------------------------------------------------------------------------
# Exception feature schema alignment
# ---------------------------------------------------------------------------

def test_exception_feature_names_match_schema(schema_loader):
    """build_exception_features must produce exactly the 19 schema columns."""
    from backend.app.services.reconciliation.exception_classification import build_exception_features

    schema = _load_schema(EXC_SCHEMA)
    required = set(schema["features"])

    row = build_exception_features(
        entity_type="bank_record",
        affected_field="amount",
        observed_value="2500.00",
        expected_value="2495.00",
        entity_amount="2500.00",
        fee_amount="90.0",
        tax_amount="16.2",
        refund_amount="0.0",
        loader=schema_loader,
    )
    produced = set(row.keys())
    missing = required - produced
    extra = produced - required
    assert not missing, f"Missing exception features: {sorted(missing)}"
    assert not extra, f"Unexpected extra exception features: {sorted(extra)}"


def test_exception_feature_count(schema_loader):
    from backend.app.services.reconciliation.exception_classification import build_exception_features
    row = build_exception_features(
        entity_type="payment",
        affected_field="reference",
        observed_value="REF001",
        expected_value="REF002",
        entity_amount="500.00",
        loader=schema_loader,
    )
    assert len(row) == 19, f"Expected 19 exception features, got {len(row)}"
