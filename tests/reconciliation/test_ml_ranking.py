from backend.app.core.constants import STATUS_AMBIGUOUS, STATUS_ML_MATCHED, STATUS_UNMATCHED
from backend.app.services.reconciliation.ml_reconciliation import MlReconciliationService


class FakeModel:
    def __init__(self, scores):
        self._scores = scores

    def score_rows(self, feature_rows):
        assert len(feature_rows) == len(self._scores)
        return list(self._scores)


def _bank_and_two_settlements():
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
    return bank, settlements


def test_ml_picks_top_candidate_when_margin_clear(schema_loader):
    bank, settlements = _bank_and_two_settlements()
    service = MlReconciliationService(
        loader=schema_loader,
        model=FakeModel([0.91, 0.20]),
    )
    result = service.score_candidates(bank, settlements)
    assert result.status == STATUS_ML_MATCHED
    assert result.matched_record_id == "STL_TOP"
    assert result.match_probability == 0.91
    assert result.runner_up_probability == 0.20
    assert result.confidence_margin == 0.71
    assert result.threshold == 0.275


def test_ml_ambiguous_when_scores_close(schema_loader):
    bank, settlements = _bank_and_two_settlements()
    service = MlReconciliationService(
        loader=schema_loader,
        model=FakeModel([0.40, 0.38]),
    )
    result = service.score_candidates(bank, settlements)
    assert result.status == STATUS_AMBIGUOUS
    assert result.matched_record_id == "STL_TOP"
    assert "ML_AMBIGUOUS_MARGIN" in result.reason_codes


def test_ml_unmatched_below_threshold(schema_loader):
    bank, settlements = _bank_and_two_settlements()
    service = MlReconciliationService(
        loader=schema_loader,
        model=FakeModel([0.10, 0.05]),
    )
    result = service.score_candidates(bank, settlements)
    assert result.status == STATUS_UNMATCHED
    assert result.matched_record_id is None
