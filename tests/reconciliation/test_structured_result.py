from backend.app.core.constants import (
    METHOD_DETERMINISTIC,
    STATUS_MATCHED,
    STATUS_UNMATCHED,
)
from backend.app.services.reconciliation.reconciliation_service import ReconciliationService


class _BankRepo:
    def __init__(self, row):
        self.row = row

    def get_by_id(self, bank_record_id):
        return self.row if self.row.get("bank_record_id") == bank_record_id else None


class _SettlementRepo:
    def __init__(self, rows):
        self.rows = rows

    def get_by_id(self, settlement_id):
        return next((row for row in self.rows if row["settlement_id"] == settlement_id), None)

    def list_for_merchant_window(self, merchant_id, center_date, window_days, limit=50):
        return [row for row in self.rows if row["merchant_id"] == merchant_id][:limit]

    def list_by_merchant(self, merchant_id, limit=200):
        return [row for row in self.rows if row["merchant_id"] == merchant_id][:limit]


def test_structured_output_deterministic_bank(schema_loader):
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
        loader=schema_loader,
        bank_repo=_BankRepo(bank),
        settlement_repo=_SettlementRepo([stl]),
    )
    result = service.run("bank_record", "BNK_1", include_ml=False, include_exception=False)
    assert result["status"] == STATUS_MATCHED
    assert result["reconciliation_method"] == METHOD_DETERMINISTIC
    assert result["matched_record_id"] == "STL_1"
    assert result["source_record_id"] == "BNK_1"
    assert "case_id" in result
    assert "reason_codes" in result
    assert "explanation_facts" in result
    assert result["exception_type"] is None


def test_unresolved_bank_skips_ml_when_disabled(schema_loader):
    bank = {
        "bank_record_id": "BNK_2",
        "amount": "10.00",
        "reference": "NOPE",
        "merchant_id": "MER_1",
        "transaction_date": "2026-08-02",
        "transaction_type": "CREDIT",
        "category": "SETTLEMENT",
        "description": "x",
    }
    stl = {
        "settlement_id": "STL_9",
        "net_amount": "99.00",
        "gross_amount": "100.00",
        "total_fees": "1",
        "total_fee_tax": "0",
        "total_refunds": "0",
        "utr": "OTHER",
        "merchant_id": "MER_1",
        "settlement_date": "2026-08-02",
        "payment_count": 1,
    }
    service = ReconciliationService(
        loader=schema_loader,
        bank_repo=_BankRepo(bank),
        settlement_repo=_SettlementRepo([stl]),
    )
    result = service.run("bank_record", "BNK_2", include_ml=False, include_exception=False)
    assert result["status"] == STATUS_UNMATCHED
    assert result["reconciliation_method"] == "unmatched"
    assert result["candidate_records"]
