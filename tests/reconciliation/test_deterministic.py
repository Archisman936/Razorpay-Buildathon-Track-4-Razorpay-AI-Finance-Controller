from backend.app.services.reconciliation.deterministic import (
    match_order_payment,
    match_settlement_bank,
    resolve_settlement_bank,
)
from backend.app.core.constants import (
    STATUS_MATCHED,
    STATUS_MATCHED_DISCREPANCY,
    STATUS_UNMATCHED,
)


def test_exact_amount_and_utr_matches():
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
    assert decision.resolved
    assert decision.status == STATUS_MATCHED
    assert decision.rule == "EXACT_AMOUNT_AND_UTR"
    assert decision.matched_record_id == "STL_1"


def test_utr_match_with_amount_discrepancy_is_linked_not_ml():
    bank = {
        "bank_record_id": "BNK_1",
        "amount": "95.00",
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
    assert decision.resolved
    assert decision.status == STATUS_MATCHED_DISCREPANCY
    assert "AMOUNT_DISCREPANCY" in decision.reason_codes
    assert decision.amount_difference == -5.0


def test_unresolved_when_neither_amount_nor_utr_exact():
    bank = {
        "bank_record_id": "BNK_1",
        "amount": "95.00",
        "reference": "AAAA",
        "merchant_id": "MER_1",
        "transaction_date": "2026-08-19",
    }
    settlement = {
        "settlement_id": "STL_1",
        "net_amount": "100.00",
        "utr": "BBBB",
        "merchant_id": "MER_1",
        "settlement_date": "2026-08-19",
    }
    decision = match_settlement_bank(bank, settlement)
    assert not decision.resolved
    assert decision.status == STATUS_UNMATCHED


def test_unique_exact_among_candidates():
    bank = {
        "bank_record_id": "BNK_1",
        "amount": "50.00",
        "reference": "UTR50",
        "merchant_id": "MER_1",
        "transaction_date": "2026-08-01",
    }
    settlements = [
        {
            "settlement_id": "STL_A",
            "net_amount": "40.00",
            "utr": "OTHER",
            "merchant_id": "MER_1",
            "settlement_date": "2026-08-01",
        },
        {
            "settlement_id": "STL_B",
            "net_amount": "50.00",
            "utr": "UTR50",
            "merchant_id": "MER_1",
            "settlement_date": "2026-08-01",
        },
    ]
    decision = resolve_settlement_bank(bank, settlements)
    assert decision.matched_record_id == "STL_B"
    assert decision.rule == "EXACT_AMOUNT_AND_UTR"


def test_order_payment_amount_mismatch():
    order = {"order_id": "ORD_1", "total_amount": "200.00", "order_date": "2026-08-01"}
    payment = {
        "payment_id": "PAY_1",
        "order_id": "ORD_1",
        "amount": "180.00",
        "payment_date": "2026-08-01",
    }
    decision = match_order_payment(order, payment)
    assert decision.status == STATUS_MATCHED_DISCREPANCY
    assert decision.matched_record_id == "PAY_1"
