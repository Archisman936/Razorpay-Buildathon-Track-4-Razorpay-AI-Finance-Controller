from backend.app.services.normalization.pipeline import NormalizationPipeline
from backend.app.services.normalization.transforms.amounts import amounts_approximately_equal
from decimal import Decimal


def test_normalization_pipeline_imports():
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


def test_amount_helper_still_present():
    assert amounts_approximately_equal(Decimal("100.00"), Decimal("100.50"), Decimal("0.02"), Decimal("1"))
