from backend.app.services.reconciliation.feature_builder import (
    add_candidate_context,
    build_candidate_feature_rows,
    pair_base_features,
)


def test_pair_features_and_ranks(schema_loader):
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
    rows = add_candidate_context(
        [pair_base_features(bank, close), pair_base_features(bank, far)]
    )
    by_id = {row["target_id"]: row for row in rows}
    assert by_id["STL_BEST"]["exact_amount_match"] == 1
    assert by_id["STL_BEST"]["is_best_amount_candidate"] == 1
    assert by_id["STL_BEST"]["is_best_reference_candidate"] == 1
    assert by_id["STL_FAR"]["candidate_rank_by_amount"] == 2
    assert by_id["STL_BEST"]["best_vs_second_best_amount_gap"] == 20.0
    assert rows[0]["candidate_count"] == 2

    aligned = build_candidate_feature_rows(bank, [close, far], schema_loader)
    schema = schema_loader.get_reconciliation_schema()
    required = schema["features"]
    assert len(required) == 35
    for row in aligned:
        for key in required:
            assert key in row
        extra = set(row) - set(required) - {"target_id"}
        assert not extra
