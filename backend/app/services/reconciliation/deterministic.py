"""Explicit, inspectable matching rules. No ML."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.core.constants import (
    PAIR_EVENT_BOOKS,
    PAIR_INVOICE_GST,
    PAIR_ORDER_INVOICE,
    PAIR_ORDER_PAYMENT,
    PAIR_PAYMENT_FEE,
    PAIR_PAYMENT_REFUND,
    PAIR_PAYMENT_SETTLEMENT,
    PAIR_SETTLEMENT_ADJUSTMENT,
    PAIR_SETTLEMENT_BANK,
    STATUS_MATCHED,
    STATUS_MATCHED_DISCREPANCY,
    STATUS_UNMATCHED,
)
from backend.app.services.reconciliation.metrics import (
    amounts_exact,
    days_between,
    normalize_id,
    to_float,
)


@dataclass
class DeterministicDecision:
    pair_type: str
    status: str
    rule: str
    reason: str
    matched_record_id: str | None = None
    source_record_id: str | None = None
    amount_difference: float | None = None
    date_difference: int | None = None
    reason_codes: list[str] = field(default_factory=list)
    explanation_facts: dict = field(default_factory=dict)
    resolved: bool = False

    @property
    def has_discrepancy(self) -> bool:
        return self.status == STATUS_MATCHED_DISCREPANCY


def _amount_diff(left, right) -> float | None:
    a = to_float(left)
    b = to_float(right)
    if a is None or b is None:
        return None
    return a - b


def match_settlement_bank(
    bank: dict,
    settlement: dict,
    amount_tolerance: float = 0.01,
) -> DeterministicDecision:
    """Production residual gate from matching v3: exact amount AND exact UTR."""
    source_id = bank.get("bank_record_id")
    target_id = settlement.get("settlement_id")
    bank_amount = bank.get("amount")
    net_amount = settlement.get("net_amount")
    amount_ok = amounts_exact(bank_amount, net_amount, amount_tolerance)
    ref_ok = bool(normalize_id(bank.get("reference"))) and (
        normalize_id(bank.get("reference")) == normalize_id(settlement.get("utr"))
    )
    date_diff = days_between(bank.get("transaction_date"), settlement.get("settlement_date"))
    facts = {
        "bank_amount": to_float(bank_amount),
        "settlement_net_amount": to_float(net_amount),
        "bank_reference": bank.get("reference"),
        "settlement_utr": settlement.get("utr"),
        "merchant_match": bank.get("merchant_id") == settlement.get("merchant_id"),
    }
    diff = _amount_diff(bank_amount, net_amount)

    if amount_ok and ref_ok:
        return DeterministicDecision(
            pair_type=PAIR_SETTLEMENT_BANK,
            status=STATUS_MATCHED,
            rule="EXACT_AMOUNT_AND_UTR",
            reason="Bank amount equals settlement net amount and normalized references match.",
            matched_record_id=target_id,
            source_record_id=source_id,
            amount_difference=diff,
            date_difference=date_diff,
            reason_codes=["EXACT_AMOUNT", "EXACT_UTR"],
            explanation_facts=facts,
            resolved=True,
        )

    if ref_ok and not amount_ok:
        return DeterministicDecision(
            pair_type=PAIR_SETTLEMENT_BANK,
            status=STATUS_MATCHED_DISCREPANCY,
            rule="EXACT_UTR_AMOUNT_MISMATCH",
            reason="UTR matches uniquely but amounts differ.",
            matched_record_id=target_id,
            source_record_id=source_id,
            amount_difference=diff,
            date_difference=date_diff,
            reason_codes=["EXACT_UTR", "AMOUNT_DISCREPANCY"],
            explanation_facts=facts,
            resolved=True,
        )

    return DeterministicDecision(
        pair_type=PAIR_SETTLEMENT_BANK,
        status=STATUS_UNMATCHED,
        rule="NO_DETERMINISTIC_SETTLEMENT_BANK_MATCH",
        reason="Amount and UTR are not jointly exact.",
        source_record_id=source_id,
        amount_difference=diff,
        date_difference=date_diff,
        reason_codes=["UNRESOLVED"],
        explanation_facts=facts,
        resolved=False,
    )


def resolve_settlement_bank(
    bank: dict,
    settlements: list[dict],
    amount_tolerance: float = 0.01,
) -> DeterministicDecision:
    """Apply settlement↔bank rules across a candidate list; unique exact wins."""
    exact_both = []
    utr_only = []
    for settlement in settlements:
        decision = match_settlement_bank(bank, settlement, amount_tolerance)
        if decision.rule == "EXACT_AMOUNT_AND_UTR":
            exact_both.append(decision)
        elif decision.rule == "EXACT_UTR_AMOUNT_MISMATCH":
            utr_only.append(decision)

    if len(exact_both) == 1:
        return exact_both[0]
    if len(exact_both) > 1:
        ids = [item.matched_record_id for item in exact_both]
        return DeterministicDecision(
            pair_type=PAIR_SETTLEMENT_BANK,
            status=STATUS_UNMATCHED,
            rule="AMBIGUOUS_EXACT_MATCHES",
            reason="Multiple settlements share exact amount and UTR.",
            source_record_id=bank.get("bank_record_id"),
            reason_codes=["AMBIGUOUS_DETERMINISTIC"],
            explanation_facts={"candidate_ids": ids},
            resolved=False,
        )
    if len(utr_only) == 1:
        return utr_only[0]
    if len(utr_only) > 1:
        return DeterministicDecision(
            pair_type=PAIR_SETTLEMENT_BANK,
            status=STATUS_UNMATCHED,
            rule="AMBIGUOUS_UTR",
            reason="Multiple settlements share the same UTR with amount mismatches.",
            source_record_id=bank.get("bank_record_id"),
            reason_codes=["AMBIGUOUS_UTR"],
            explanation_facts={
                "candidate_ids": [item.matched_record_id for item in utr_only],
            },
            resolved=False,
        )
    empty = match_settlement_bank(bank, {}, amount_tolerance)
    empty.reason = "No settlement satisfied exact amount+UTR rules."
    return empty


def match_order_payment(order: dict, payment: dict) -> DeterministicDecision:
    linked = payment.get("order_id") == order.get("order_id")
    amount_ok = amounts_exact(payment.get("amount"), order.get("total_amount"))
    return _fk_amount_decision(
        PAIR_ORDER_PAYMENT,
        "ORDER_ID_AND_AMOUNT",
        linked,
        amount_ok,
        payment.get("payment_id"),
        order.get("order_id"),
        _amount_diff(payment.get("amount"), order.get("total_amount")),
        days_between(payment.get("payment_date"), order.get("order_date")),
        {"order_id": order.get("order_id"), "payment_order_id": payment.get("order_id")},
    )


def match_order_invoice(order: dict, invoice: dict) -> DeterministicDecision:
    linked = invoice.get("order_id") == order.get("order_id")
    amount_ok = amounts_exact(invoice.get("total_amount"), order.get("total_amount"))
    return _fk_amount_decision(
        PAIR_ORDER_INVOICE,
        "ORDER_ID_AND_AMOUNT",
        linked,
        amount_ok,
        invoice.get("invoice_id"),
        order.get("order_id"),
        _amount_diff(invoice.get("total_amount"), order.get("total_amount")),
        days_between(invoice.get("invoice_date"), order.get("order_date")),
        {"order_id": order.get("order_id"), "invoice_order_id": invoice.get("order_id")},
    )


def match_payment_fee(payment: dict, fee: dict) -> DeterministicDecision:
    linked = fee.get("payment_id") == payment.get("payment_id")
    return _fk_amount_decision(
        PAIR_PAYMENT_FEE,
        "PAYMENT_ID_LINK",
        linked,
        True,
        fee.get("fee_id"),
        payment.get("payment_id"),
        None,
        None,
        {"fee_amount": to_float(fee.get("fee_amount"))},
    )


def match_payment_refund(payment: dict, refund: dict) -> DeterministicDecision:
    linked = refund.get("payment_id") == payment.get("payment_id")
    payment_amount = to_float(payment.get("amount"))
    refund_amount = to_float(refund.get("refund_amount"))
    amount_ok = (
        refund_amount is not None
        and payment_amount is not None
        and refund_amount <= payment_amount + 0.01
    )
    return _fk_amount_decision(
        PAIR_PAYMENT_REFUND,
        "PAYMENT_ID_REFUND_LEQ_PAYMENT",
        linked,
        amount_ok,
        refund.get("refund_id"),
        payment.get("payment_id"),
        _amount_diff(refund_amount, payment_amount),
        days_between(refund.get("refund_date"), payment.get("payment_date")),
        {"refund_type": refund.get("refund_type")},
    )


def match_payment_settlement(payment: dict, link: dict) -> DeterministicDecision:
    linked = link.get("payment_id") == payment.get("payment_id")
    amount_ok = amounts_exact(link.get("allocated_amount"), payment.get("amount")) or (
        link.get("allocated_amount") is None and linked
    )
    return _fk_amount_decision(
        PAIR_PAYMENT_SETTLEMENT,
        "SETTLEMENT_PAYMENTS_LINK",
        linked,
        amount_ok,
        link.get("settlement_id"),
        payment.get("payment_id"),
        _amount_diff(link.get("allocated_amount"), payment.get("amount")),
        None,
        {"allocated_amount": to_float(link.get("allocated_amount"))},
    )


def match_invoice_gst(invoice: dict, gst: dict) -> DeterministicDecision:
    linked = gst.get("invoice_id") == invoice.get("invoice_id")
    tax_ok = amounts_exact(gst.get("total_tax"), invoice.get("total_tax"))
    amount_ok = amounts_exact(gst.get("total_amount"), invoice.get("total_amount"))
    return _fk_amount_decision(
        PAIR_INVOICE_GST,
        "INVOICE_ID_AND_TAX",
        linked,
        tax_ok and amount_ok,
        gst.get("gst_record_id"),
        invoice.get("invoice_id"),
        _amount_diff(gst.get("total_amount"), invoice.get("total_amount")),
        None,
        {
            "invoice_total_tax": to_float(invoice.get("total_tax")),
            "gst_total_tax": to_float(gst.get("total_tax")),
        },
    )


def match_settlement_adjustment(settlement: dict, adjustment: dict) -> DeterministicDecision:
    linked = adjustment.get("settlement_id") == settlement.get("settlement_id")
    return _fk_amount_decision(
        PAIR_SETTLEMENT_ADJUSTMENT,
        "SETTLEMENT_ID_LINK",
        linked,
        True,
        adjustment.get("adjustment_id"),
        settlement.get("settlement_id"),
        to_float(adjustment.get("amount")),
        days_between(adjustment.get("adjustment_date"), settlement.get("settlement_date")),
        {"adjustment_type": adjustment.get("adjustment_type")},
    )


def match_event_books(reference_id: str, entries: list[dict]) -> DeterministicDecision:
    if not entries:
        return DeterministicDecision(
            pair_type=PAIR_EVENT_BOOKS,
            status=STATUS_UNMATCHED,
            rule="NO_LEDGER_ENTRIES",
            reason="No book entries reference this entity.",
            source_record_id=reference_id,
            reason_codes=["MISSING_RECORD"],
            resolved=False,
        )
    debit = sum(to_float(row.get("debit")) or 0.0 for row in entries)
    credit = sum(to_float(row.get("credit")) or 0.0 for row in entries)
    balanced = abs(debit - credit) < 0.01
    status = STATUS_MATCHED if balanced else STATUS_MATCHED_DISCREPANCY
    return DeterministicDecision(
        pair_type=PAIR_EVENT_BOOKS,
        status=status,
        rule="REFERENCE_ID_AND_DEBIT_CREDIT",
        reason="Ledger entries found; debit/credit compared.",
        matched_record_id=entries[0].get("entry_id"),
        source_record_id=reference_id,
        amount_difference=debit - credit,
        reason_codes=["LEDGER_BALANCED"] if balanced else ["LEDGER_IMBALANCE"],
        explanation_facts={"debit_sum": debit, "credit_sum": credit, "entry_count": len(entries)},
        resolved=True,
    )


def _fk_amount_decision(
    pair_type: str,
    rule: str,
    linked: bool,
    amount_ok: bool,
    matched_id,
    source_id,
    amount_difference,
    date_difference,
    facts: dict,
) -> DeterministicDecision:
    if linked and amount_ok:
        return DeterministicDecision(
            pair_type=pair_type,
            status=STATUS_MATCHED,
            rule=rule,
            reason="Foreign key and amount rules satisfied.",
            matched_record_id=matched_id,
            source_record_id=source_id,
            amount_difference=amount_difference,
            date_difference=date_difference,
            reason_codes=["FK_MATCH", "AMOUNT_OK"],
            explanation_facts=facts,
            resolved=True,
        )
    if linked and not amount_ok:
        return DeterministicDecision(
            pair_type=pair_type,
            status=STATUS_MATCHED_DISCREPANCY,
            rule=rule,
            reason="Records are linked but amounts (or tax) do not match.",
            matched_record_id=matched_id,
            source_record_id=source_id,
            amount_difference=amount_difference,
            date_difference=date_difference,
            reason_codes=["FK_MATCH", "AMOUNT_DISCREPANCY"],
            explanation_facts=facts,
            resolved=True,
        )
    return DeterministicDecision(
        pair_type=pair_type,
        status=STATUS_UNMATCHED,
        rule=rule,
        reason="Required identifier link is missing.",
        source_record_id=source_id,
        amount_difference=amount_difference,
        date_difference=date_difference,
        reason_codes=["MISSING_RECORD"],
        explanation_facts=facts,
        resolved=False,
    )
