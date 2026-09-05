from backend.app.services.reconciliation.exception_classification import (
    build_exception_features,
    features_from_bank_settlement,
)


def test_exception_features_match_schema(schema_loader):
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
        loader=schema_loader,
    )
    schema = schema_loader.get_exception_schema()
    assert set(row) == set(schema["features"])
    assert row["entity_type"] == "BNK"
    assert row["affected_field"] == "amount"
    assert row["value_is_numeric_pair"] == 1
    assert abs(row["value_numeric_abs_diff"] - 5.0) < 1e-9
    assert row["value_exact_match"] == 0


def test_bank_settlement_routes_amount_field(schema_loader):
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
    row = features_from_bank_settlement(bank, settlement, schema_loader)
    assert row["affected_field"] == "amount"


class FakeClassifier:
    def predict(self, feature_row):
        assert "entity_type" in feature_row
        return {
            "exception_type": "AMOUNT_DISCREPANCY",
            "confidence": 0.88,
            "probabilities": {"AMOUNT_DISCREPANCY": 0.88},
        }


def test_exception_service_uses_adapter(schema_loader):
    from backend.app.services.reconciliation.exception_classification import (
        ExceptionClassificationService,
        build_exception_features,
    )

    service = ExceptionClassificationService(
        loader=schema_loader,
        classifier=FakeClassifier(),
    )
    features = build_exception_features(
        entity_type="payment",
        affected_field="amount",
        observed_value="1",
        expected_value="2",
        entity_amount="1",
        loader=schema_loader,
    )
    result = service.classify(features)
    assert result["exception_type"] == "AMOUNT_DISCREPANCY"
