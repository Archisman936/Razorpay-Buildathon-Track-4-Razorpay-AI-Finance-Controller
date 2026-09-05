"""Tool adapters for existing project components."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.app.core.logging import get_logger
from backend.app.database.repositories.bank_repository import BankRepository
from backend.app.database.repositories.entity_repository import EntityRepository
from backend.app.database.repositories.payment_repository import PaymentRepository
from backend.app.database.repositories.settlement_repository import SettlementRepository
from backend.app.database.connection import fetch_one, fetch_all
from backend.app.services.reconciliation.reconciliation_service import ReconciliationService, RecordNotFoundError

logger = get_logger(__name__)


class ReconciliationTool:
    """Adapter for the existing reconciliation service."""

    def __init__(self, reconciliation_service: Optional[ReconciliationService] = None):
        self.reconciliation_service = reconciliation_service or ReconciliationService()

    def get_reconciliation_result(
        self,
        source_type: str,
        source_id: str,
        include_ml: bool = True,
        include_exception: bool = True,
    ) -> Dict[str, Any]:
        """Get reconciliation result for a specific record."""
        try:
            result = self.reconciliation_service.run(
                source_type=source_type,
                source_id=source_id,
                include_ml=include_ml,
                include_exception=include_exception,
            )
            logger.info("Retrieved reconciliation result for %s: %s", source_type, source_id)
            return result
        except RecordNotFoundError as e:
            logger.warning("Record not found: %s", e)
            return {"error": str(e), "source_type": source_type, "source_id": source_id}
        except Exception as e:
            logger.error("Failed to get reconciliation result: %s", e)
            return {"error": str(e), "source_type": source_type, "source_id": source_id}

    def get_unmatched_transactions(
        self,
        source_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get unmatched transactions from the database."""
        try:
            if source_type == "bank_record":
                sql = """
                    SELECT * FROM bank_records
                    WHERE settlement_id IS NULL
                    ORDER BY transaction_date DESC
                    LIMIT %s
                """
                results = fetch_all(sql, (limit,))
            elif source_type == "payment":
                sql = """
                    SELECT p.* FROM payments p
                    LEFT JOIN settlement_payments sp ON p.payment_id = sp.payment_id
                    WHERE sp.settlement_id IS NULL
                    ORDER BY p.payment_date DESC
                    LIMIT %s
                """
                results = fetch_all(sql, (limit,))
            else:
                # Generic unmatched query
                sql = """
                    SELECT 'bank_record' as source_type, bank_record_id as id, transaction_date as date
                    FROM bank_records WHERE settlement_id IS NULL
                    UNION ALL
                    SELECT 'payment' as source_type, payment_id as id, payment_date as date
                    FROM payments p
                    LEFT JOIN settlement_payments sp ON p.payment_id = sp.payment_id
                    WHERE sp.settlement_id IS NULL
                    ORDER BY date DESC
                    LIMIT %s
                """
                results = fetch_all(sql, (limit,))

            logger.info("Retrieved %d unmatched records", len(results))
            return results

        except Exception as e:
            logger.error("Failed to get unmatched transactions: %s", e)
            return [{"error": str(e)}]

    def get_reconciliation_summary(self) -> Dict[str, Any]:
        """Get summary statistics of reconciliation status."""
        try:
            # Count unmatched bank records
            unmatched_bank = fetch_one(
                "SELECT COUNT(*) as count FROM bank_records WHERE settlement_id IS NULL"
            )

            # Count unmatched payments
            unmatched_payments = fetch_one("""
                SELECT COUNT(*) as count FROM payments p
                LEFT JOIN settlement_payments sp ON p.payment_id = sp.payment_id
                WHERE sp.settlement_id IS NULL
            """)

            # Total counts
            total_bank = fetch_one("SELECT COUNT(*) as count FROM bank_records")
            total_payments = fetch_one("SELECT COUNT(*) as count FROM payments")

            summary = {
                "unmatched_bank_records": unmatched_bank.get("count", 0) if unmatched_bank else 0,
                "unmatched_payments": unmatched_payments.get("count", 0) if unmatched_payments else 0,
                "total_bank_records": total_bank.get("count", 0) if total_bank else 0,
                "total_payments": total_payments.get("count", 0) if total_payments else 0,
            }

            logger.info("Retrieved reconciliation summary: %s", summary)
            return summary

        except Exception as e:
            logger.error("Failed to get reconciliation summary: %s", e)
            return {"error": str(e)}


class DatabaseTool:
    """Adapter for database queries."""

    def __init__(self):
        self.bank_repo = BankRepository()
        self.settlement_repo = SettlementRepository()
        self.payment_repo = PaymentRepository()
        self.entity_repo = EntityRepository()

    def get_transaction(self, transaction_id: str, transaction_type: str) -> Optional[Dict[str, Any]]:
        """Get a specific transaction by ID and type."""
        try:
            if transaction_type == "bank_record":
                return self.bank_repo.get_by_id(transaction_id)
            elif transaction_type == "payment":
                return self.payment_repo.get_by_id(transaction_id)
            elif transaction_type == "settlement":
                return self.settlement_repo.get_by_id(transaction_id)
            else:
                logger.warning("Unknown transaction type: %s", transaction_type)
                return None
        except Exception as e:
            logger.error("Failed to get transaction: %s", e)
            return None

    def get_payment_details(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed payment information including related records."""
        try:
            payment = self.payment_repo.get_by_id(payment_id)
            if not payment:
                return None

            # Get related order
            order = self.payment_repo.get_order(payment.get("order_id"))

            # Get fees
            fees = self.payment_repo.list_fees(payment_id)

            # Get refunds
            refunds = self.payment_repo.list_refunds(payment_id)

            # Get settlement links
            settlement_links = self.payment_repo.list_settlement_links(payment_id)

            return {
                "payment": payment,
                "order": order,
                "fees": fees,
                "refunds": refunds,
                "settlement_links": settlement_links,
            }

        except Exception as e:
            logger.error("Failed to get payment details: %s", e)
            return None

    def get_settlement_details(self, settlement_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed settlement information."""
        try:
            settlement = self.settlement_repo.get_by_id(settlement_id)
            if not settlement:
                return None

            # Get adjustments
            adjustments = self.entity_repo.list_adjustments_for_settlement(settlement_id)

            # Get linked payments
            linked_payments = fetch_all(
                "SELECT sp.*, p.* FROM settlement_payments sp "
                "JOIN payments p ON sp.payment_id = p.payment_id "
                "WHERE sp.settlement_id = %s",
                (settlement_id,),
            )

            return {
                "settlement": settlement,
                "adjustments": adjustments,
                "linked_payments": linked_payments,
            }

        except Exception as e:
            logger.error("Failed to get settlement details: %s", e)
            return None


class MLTool:
    """Adapter for ML model results."""

    def __init__(self):
        # ML results are already embedded in reconciliation service
        # This tool provides a clean interface for accessing them
        pass

    def get_ml_analysis_from_reconciliation(self, reconciliation_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract ML analysis from reconciliation result."""
        ml_data = {}

        if "match_probability" in reconciliation_result:
            ml_data["match_probability"] = reconciliation_result["match_probability"]

        if "runner_up_probability" in reconciliation_result:
            ml_data["runner_up_probability"] = reconciliation_result["runner_up_probability"]

        if "confidence_margin" in reconciliation_result:
            ml_data["confidence_margin"] = reconciliation_result["confidence_margin"]

        if "exception_type" in reconciliation_result:
            ml_data["exception_type"] = reconciliation_result["exception_type"]

        if "exception_confidence" in reconciliation_result:
            ml_data["exception_confidence"] = reconciliation_result["exception_confidence"]

        if "exception" in reconciliation_result:
            ml_data["exception_details"] = reconciliation_result["exception"]

        return ml_data if ml_data else None
