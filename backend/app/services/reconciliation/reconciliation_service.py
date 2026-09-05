"""Orchestrate deterministic rules, residual ML matching, and exception classification."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from backend.app.core.config import Settings, get_settings
from backend.app.core.constants import (
    EXCEPTION_WHEN_STATUS,
    METHOD_AMBIGUOUS,
    METHOD_DETERMINISTIC,
    METHOD_ML,
    METHOD_UNMATCHED,
    STATUS_AMBIGUOUS,
    STATUS_MATCHED,
    STATUS_MATCHED_DISCREPANCY,
    STATUS_ML_MATCHED,
    STATUS_UNMATCHED,
)
from backend.app.core.logging import get_logger
from backend.app.database.repositories.bank_repository import BankRepository
from backend.app.database.repositories.entity_repository import EntityRepository
from backend.app.database.repositories.payment_repository import PaymentRepository
from backend.app.database.repositories.settlement_repository import SettlementRepository
from backend.app.ml.model_loader import ModelArtifactError, ModelLoader, get_model_loader
from backend.app.services.reconciliation.candidate_generation import generate_settlement_candidates
from backend.app.services.reconciliation.deterministic import (
    DeterministicDecision,
    match_event_books,
    match_invoice_gst,
    match_order_invoice,
    match_order_payment,
    match_payment_fee,
    match_payment_refund,
    match_payment_settlement,
    match_settlement_adjustment,
    resolve_settlement_bank,
)
from backend.app.services.reconciliation.exception_classification import (
    ExceptionClassificationService,
    build_exception_features,
    features_from_bank_settlement,
)
from backend.app.services.reconciliation.ml_reconciliation import MlReconciliationService
from backend.app.services.reconciliation.metrics import parse_date, to_float

logger = get_logger(__name__)


class RecordNotFoundError(LookupError):
    pass


def _case_id(source_type: str, source_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"CASE_{source_type}_{source_id}_{stamp}_{uuid4().hex[:6]}"


def _method_for(status: str, used_ml: bool) -> str:
    if status == STATUS_AMBIGUOUS:
        return METHOD_AMBIGUOUS
    if status == STATUS_UNMATCHED:
        return METHOD_UNMATCHED
    if used_ml or status == STATUS_ML_MATCHED:
        return METHOD_ML
    return METHOD_DETERMINISTIC


class ReconciliationService:
    def __init__(
        self,
        settings: Settings | None = None,
        loader: ModelLoader | None = None,
        bank_repo: BankRepository | None = None,
        settlement_repo: SettlementRepository | None = None,
        payment_repo: PaymentRepository | None = None,
        entity_repo: EntityRepository | None = None,
        ml_service: MlReconciliationService | None = None,
        exception_service: ExceptionClassificationService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.loader = loader or get_model_loader()
        self.bank_repo = bank_repo or BankRepository()
        self.settlement_repo = settlement_repo or SettlementRepository()
        self.payment_repo = payment_repo or PaymentRepository()
        self.entity_repo = entity_repo or EntityRepository()
        self.ml_service = ml_service or MlReconciliationService(
            loader=self.loader, settings=self.settings
        )
        self.exception_service = exception_service or ExceptionClassificationService(
            loader=self.loader
        )

    def run(
        self,
        source_type: str,
        source_id: str,
        include_ml: bool = True,
        include_exception: bool = True,
    ) -> dict:
        kind = source_type.strip().lower()
        if kind in {"bank", "bank_record", "bank_records"}:
            return self._run_bank(source_id, include_ml, include_exception)
        if kind in {"payment", "payments"}:
            return self._run_payment(source_id, include_exception)
        if kind in {"order", "orders"}:
            return self._run_order(source_id, include_exception)
        if kind in {"invoice", "invoices"}:
            return self._run_invoice(source_id, include_exception)
        if kind in {"settlement", "settlements"}:
            return self._run_settlement(source_id, include_exception)
        raise ValueError(f"Unsupported source_type '{source_type}'")

    def _run_bank(self, source_id: str, include_ml: bool, include_exception: bool) -> dict:
        bank = self.bank_repo.get_by_id(source_id)
        if not bank:
            raise RecordNotFoundError(f"bank_record not found: {source_id}")

        settlements = self._settlements_for_bank(bank)
        decision = resolve_settlement_bank(
            bank, settlements, self.settings.amount_exact_tolerance
        )
        used_ml = False
        ml_result = None
        matched_settlement = None
        candidates: list[dict] = []

        if decision.resolved:
            if decision.matched_record_id:
                matched_settlement = self.settlement_repo.get_by_id(decision.matched_record_id)
            status = decision.status
            reason_codes = list(decision.reason_codes)
            facts = dict(decision.explanation_facts)
            amount_difference = decision.amount_difference
            date_difference = decision.date_difference
            matched_id = decision.matched_record_id
            rule = decision.rule
            reason = decision.reason
        else:
            pool = generate_settlement_candidates(bank, settlements, self.settings)
            candidates = [
                {"record_id": row.get("settlement_id"), "utr": row.get("utr")}
                for row in pool
            ]
            if include_ml:
                try:
                    ml_result = self.ml_service.score_candidates(bank, pool)
                    used_ml = True
                    status = ml_result.status
                    matched_id = ml_result.matched_record_id
                    reason_codes = list(ml_result.reason_codes)
                    facts = dict(ml_result.explanation_facts)
                    candidates = ml_result.candidate_records
                    if matched_id:
                        matched_settlement = self.settlement_repo.get_by_id(matched_id)
                    amount_difference = (
                        candidates[0].get("absolute_amount_difference") if candidates else None
                    )
                    date_difference = (
                        candidates[0].get("date_difference_days") if candidates else None
                    )
                    rule = "ML_CANDIDATE_RANKING"
                    reason = "Deterministic rules did not resolve; residual model scored candidates."
                except ModelArtifactError as exc:
                    logger.warning("ML reconciliation skipped: %s", exc)
                    status = STATUS_UNMATCHED
                    matched_id = None
                    reason_codes = ["ML_UNAVAILABLE", *decision.reason_codes]
                    facts = {**decision.explanation_facts, "ml_error": str(exc)}
                    amount_difference = decision.amount_difference
                    date_difference = decision.date_difference
                    rule = decision.rule
                    reason = f"Deterministic unresolved and ML artifacts missing: {exc}"
            else:
                status = STATUS_UNMATCHED
                matched_id = None
                reason_codes = list(decision.reason_codes)
                facts = dict(decision.explanation_facts)
                amount_difference = decision.amount_difference
                date_difference = decision.date_difference
                rule = decision.rule
                reason = decision.reason

        exception_payload = None
        if include_exception and status in EXCEPTION_WHEN_STATUS:
            exception_payload = self._classify_bank(bank, matched_settlement)

        return self._result(
            source_type="bank_record",
            source_id=source_id,
            status=status,
            method=_method_for(status, used_ml),
            matched_id=matched_id,
            candidates=candidates,
            ml_result=ml_result,
            exception_payload=exception_payload,
            amount_difference=amount_difference,
            date_difference=date_difference,
            reason_codes=reason_codes,
            explanation_facts={
                **facts,
                "rule": rule,
                "reason": reason,
                "pair_type": "SETTLEMENT_BANK",
            },
        )

    def _run_payment(self, source_id: str, include_exception: bool) -> dict:
        payment = self.payment_repo.get_by_id(source_id)
        if not payment:
            raise RecordNotFoundError(f"payment not found: {source_id}")
        order = self.payment_repo.get_order(payment.get("order_id"))
        fees = self.payment_repo.list_fees(source_id)
        refunds = self.payment_repo.list_refunds(source_id)
        links = self.payment_repo.list_settlement_links(source_id)
        books = self.entity_repo.list_books_for_reference(source_id)

        decisions: list[DeterministicDecision] = []
        if order:
            decisions.append(match_order_payment(order, payment))
        else:
            decisions.append(
                DeterministicDecision(
                    pair_type="ORDER_PAYMENT",
                    status=STATUS_UNMATCHED,
                    rule="ORDER_ID_AND_AMOUNT",
                    reason="Linked order is missing.",
                    source_record_id=source_id,
                    reason_codes=["MISSING_RECORD"],
                    resolved=False,
                )
            )
        for fee in fees:
            decisions.append(match_payment_fee(payment, fee))
        if not fees:
            decisions.append(
                DeterministicDecision(
                    pair_type="PAYMENT_FEE",
                    status=STATUS_UNMATCHED,
                    rule="PAYMENT_ID_LINK",
                    reason="No fee rows for this payment.",
                    source_record_id=source_id,
                    reason_codes=["MISSING_RECORD"],
                    resolved=False,
                )
            )
        for refund in refunds:
            decisions.append(match_payment_refund(payment, refund))
        for link in links:
            decisions.append(match_payment_settlement(payment, link))
        decisions.append(match_event_books(source_id, books))

        primary = _worst_decision(decisions)
        exception_payload = None
        if include_exception and primary.status in EXCEPTION_WHEN_STATUS:
            counterpart = order.get("total_amount") if order else None
            exception_payload = self._classify_generic(
                entity_type="payment",
                affected_field="amount" if primary.status == STATUS_MATCHED_DISCREPANCY else "order_id",
                observed_value=payment.get("amount") if primary.status == STATUS_MATCHED_DISCREPANCY else payment.get("order_id"),
                expected_value=counterpart if primary.status == STATUS_MATCHED_DISCREPANCY else payment.get("order_id"),
                entity_amount=payment.get("amount"),
                fee_amount=fees[0].get("fee_amount") if fees else None,
                tax_amount=fees[0].get("tax_amount") if fees else None,
                refund_amount=refunds[0].get("refund_amount") if refunds else None,
            )

        return self._result(
            source_type="payment",
            source_id=source_id,
            status=primary.status,
            method=_method_for(primary.status, False),
            matched_id=primary.matched_record_id or (order.get("order_id") if order else None),
            candidates=[],
            ml_result=None,
            exception_payload=exception_payload,
            amount_difference=primary.amount_difference,
            date_difference=primary.date_difference,
            reason_codes=_merge_codes(decisions),
            explanation_facts={
                "rule": primary.rule,
                "reason": primary.reason,
                "related": [d.__dict__ for d in decisions],
            },
        )

    def _run_order(self, source_id: str, include_exception: bool) -> dict:
        order = self.payment_repo.get_order(source_id)
        if not order:
            raise RecordNotFoundError(f"order not found: {source_id}")
        payments = self.payment_repo.list_by_order(source_id)
        invoices = self.entity_repo.list_invoices_for_order(source_id)
        decisions = []
        for payment in payments:
            decisions.append(match_order_payment(order, payment))
        if not payments:
            decisions.append(
                DeterministicDecision(
                    pair_type="ORDER_PAYMENT",
                    status=STATUS_UNMATCHED,
                    rule="ORDER_ID_AND_AMOUNT",
                    reason="No payments for this order.",
                    source_record_id=source_id,
                    reason_codes=["MISSING_RECORD"],
                    resolved=False,
                )
            )
        for invoice in invoices:
            decisions.append(match_order_invoice(order, invoice))
        primary = _worst_decision(decisions)
        exception_payload = None
        if include_exception and primary.status in EXCEPTION_WHEN_STATUS:
            exception_payload = self._classify_generic(
                entity_type="order",
                affected_field="total_amount",
                observed_value=order.get("total_amount"),
                expected_value=payments[0].get("amount") if payments else None,
                entity_amount=order.get("total_amount"),
            )
        matched = None
        if payments:
            matched = payments[0].get("payment_id")
        elif invoices:
            matched = invoices[0].get("invoice_id")
        return self._result(
            source_type="order",
            source_id=source_id,
            status=primary.status,
            method=_method_for(primary.status, False),
            matched_id=matched,
            candidates=[],
            ml_result=None,
            exception_payload=exception_payload,
            amount_difference=primary.amount_difference,
            date_difference=primary.date_difference,
            reason_codes=_merge_codes(decisions),
            explanation_facts={"rule": primary.rule, "related": [d.__dict__ for d in decisions]},
        )

    def _run_invoice(self, source_id: str, include_exception: bool) -> dict:
        invoice = self.entity_repo.get_invoice(source_id)
        if not invoice:
            raise RecordNotFoundError(f"invoice not found: {source_id}")
        order = self.payment_repo.get_order(invoice.get("order_id"))
        gst_rows = self.entity_repo.list_gst_for_invoice(source_id)
        decisions = []
        if order:
            decisions.append(match_order_invoice(order, invoice))
        for gst in gst_rows:
            decisions.append(match_invoice_gst(invoice, gst))
        if not gst_rows:
            decisions.append(
                DeterministicDecision(
                    pair_type="INVOICE_GST",
                    status=STATUS_UNMATCHED,
                    rule="INVOICE_ID_AND_TAX",
                    reason="No GST record for this invoice.",
                    source_record_id=source_id,
                    reason_codes=["MISSING_RECORD"],
                    resolved=False,
                )
            )
        primary = _worst_decision(decisions)
        exception_payload = None
        if include_exception and primary.status in EXCEPTION_WHEN_STATUS:
            exception_payload = self._classify_generic(
                entity_type="invoice",
                affected_field="total_tax" if gst_rows else "invoice_id",
                observed_value=invoice.get("total_tax") if gst_rows else invoice.get("invoice_id"),
                expected_value=gst_rows[0].get("total_tax") if gst_rows else None,
                entity_amount=invoice.get("total_amount"),
                tax_amount=invoice.get("total_tax"),
            )
        return self._result(
            source_type="invoice",
            source_id=source_id,
            status=primary.status,
            method=_method_for(primary.status, False),
            matched_id=gst_rows[0].get("gst_record_id") if gst_rows else invoice.get("order_id"),
            candidates=[],
            ml_result=None,
            exception_payload=exception_payload,
            amount_difference=primary.amount_difference,
            date_difference=primary.date_difference,
            reason_codes=_merge_codes(decisions),
            explanation_facts={"rule": primary.rule, "related": [d.__dict__ for d in decisions]},
        )

    def _run_settlement(self, source_id: str, include_exception: bool) -> dict:
        settlement = self.settlement_repo.get_by_id(source_id)
        if not settlement:
            raise RecordNotFoundError(f"settlement not found: {source_id}")
        adjustments = self.entity_repo.list_adjustments_for_settlement(source_id)
        books = self.entity_repo.list_books_for_reference(source_id)
        decisions = [match_event_books(source_id, books)]
        for adjustment in adjustments:
            decisions.append(match_settlement_adjustment(settlement, adjustment))
        expected_net = (
            (to_float(settlement.get("gross_amount")) or 0)
            - (to_float(settlement.get("total_fees")) or 0)
            - (to_float(settlement.get("total_fee_tax")) or 0)
            - (to_float(settlement.get("total_refunds")) or 0)
            + (to_float(settlement.get("total_adjustments")) or 0)
        )
        actual_net = to_float(settlement.get("net_amount"))
        arith_ok = actual_net is not None and abs(actual_net - expected_net) < 0.05
        if not arith_ok:
            decisions.append(
                DeterministicDecision(
                    pair_type="SETTLEMENT_ARITHMETIC",
                    status=STATUS_MATCHED_DISCREPANCY,
                    rule="NET_EQUALS_GROSS_MINUS_FEES_TAX_REFUNDS_PLUS_ADJ",
                    reason="Settlement net amount does not equal the documented identity.",
                    source_record_id=source_id,
                    amount_difference=None if actual_net is None else actual_net - expected_net,
                    reason_codes=["AMOUNT_DISCREPANCY"],
                    explanation_facts={"expected_net": expected_net, "actual_net": actual_net},
                    resolved=True,
                )
            )
        primary = _worst_decision(decisions)
        exception_payload = None
        if include_exception and primary.status in EXCEPTION_WHEN_STATUS:
            exception_payload = self._classify_generic(
                entity_type="settlement",
                affected_field="net_amount",
                observed_value=actual_net,
                expected_value=expected_net,
                entity_amount=actual_net,
                fee_amount=settlement.get("total_fees"),
                tax_amount=settlement.get("total_fee_tax"),
                refund_amount=settlement.get("total_refunds"),
                adjustment_amount=settlement.get("total_adjustments"),
            )
        return self._result(
            source_type="settlement",
            source_id=source_id,
            status=primary.status if arith_ok or primary.status != STATUS_MATCHED else STATUS_MATCHED_DISCREPANCY,
            method=_method_for(primary.status, False),
            matched_id=source_id,
            candidates=[],
            ml_result=None,
            exception_payload=exception_payload,
            amount_difference=None if actual_net is None else actual_net - expected_net,
            date_difference=None,
            reason_codes=_merge_codes(decisions),
            explanation_facts={
                "expected_net": expected_net,
                "actual_net": actual_net,
                "related": [d.__dict__ for d in decisions],
            },
        )

    def _settlements_for_bank(self, bank: dict) -> list[dict]:
        center = parse_date(bank.get("transaction_date"))
        merchant_id = bank.get("merchant_id")
        if center:
            rows = self.settlement_repo.list_for_merchant_window(
                merchant_id,
                center,
                self.settings.candidate_window_days,
                limit=max(self.settings.max_candidates * 3, 50),
            )
            if rows:
                return rows
        return self.settlement_repo.list_by_merchant(merchant_id)

    def _classify_bank(self, bank: dict, settlement: dict | None) -> dict | None:
        try:
            features = features_from_bank_settlement(bank, settlement, self.loader)
            return self.exception_service.classify(features)
        except ModelArtifactError as exc:
            logger.warning("exception classifier skipped: %s", exc)
            return {"exception_type": None, "error": str(exc)}

    def _classify_generic(self, **kwargs) -> dict | None:
        try:
            features = build_exception_features(loader=self.loader, **kwargs)
            return self.exception_service.classify(features)
        except ModelArtifactError as exc:
            logger.warning("exception classifier skipped: %s", exc)
            return {"exception_type": None, "error": str(exc)}

    def _result(
        self,
        *,
        source_type: str,
        source_id: str,
        status: str,
        method: str,
        matched_id,
        candidates,
        ml_result,
        exception_payload,
        amount_difference,
        date_difference,
        reason_codes,
        explanation_facts,
    ) -> dict:
        exception_type = None
        exception_confidence = None
        if exception_payload:
            exception_type = exception_payload.get("exception_type")
            exception_confidence = exception_payload.get("confidence")
        return {
            "case_id": _case_id(source_type, source_id),
            "source_record_id": source_id,
            "source_type": source_type,
            "status": status,
            "reconciliation_method": method,
            "matched_record_id": matched_id,
            "candidate_records": candidates,
            "match_probability": None if ml_result is None else ml_result.match_probability,
            "runner_up_probability": None if ml_result is None else ml_result.runner_up_probability,
            "confidence_margin": None if ml_result is None else ml_result.confidence_margin,
            "exception_type": exception_type,
            "exception_confidence": exception_confidence,
            "exception": exception_payload,
            "amount_difference": amount_difference,
            "date_difference": date_difference,
            "reason_codes": reason_codes,
            "explanation_facts": explanation_facts,
        }


def _worst_decision(decisions: list[DeterministicDecision]) -> DeterministicDecision:
    rank = {
        STATUS_UNMATCHED: 3,
        STATUS_AMBIGUOUS: 3,
        STATUS_MATCHED_DISCREPANCY: 2,
        STATUS_ML_MATCHED: 1,
        STATUS_MATCHED: 0,
    }
    return max(decisions, key=lambda item: rank.get(item.status, 0))


def _merge_codes(decisions: list[DeterministicDecision]) -> list[str]:
    codes: list[str] = []
    for decision in decisions:
        for code in decision.reason_codes:
            if code not in codes:
                codes.append(code)
    return codes
