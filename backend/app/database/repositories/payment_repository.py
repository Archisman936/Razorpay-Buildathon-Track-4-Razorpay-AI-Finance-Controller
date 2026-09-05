from __future__ import annotations

from backend.app.database.connection import fetch_all, fetch_one


class PaymentRepository:
    def get_by_id(self, payment_id: str) -> dict | None:
        return fetch_one(
            "SELECT * FROM payments WHERE payment_id = %s",
            (payment_id,),
        )

    def list_by_order(self, order_id: str) -> list[dict]:
        return fetch_all(
            "SELECT * FROM payments WHERE order_id = %s ORDER BY payment_date",
            (order_id,),
        )

    def get_order(self, order_id: str) -> dict | None:
        return fetch_one(
            "SELECT * FROM orders WHERE order_id = %s",
            (order_id,),
        )

    def list_fees(self, payment_id: str) -> list[dict]:
        return fetch_all(
            "SELECT * FROM fees WHERE payment_id = %s",
            (payment_id,),
        )

    def list_refunds(self, payment_id: str) -> list[dict]:
        return fetch_all(
            "SELECT * FROM refunds WHERE payment_id = %s",
            (payment_id,),
        )

    def list_settlement_links(self, payment_id: str) -> list[dict]:
        return fetch_all(
            """
            SELECT sp.*, s.net_amount, s.utr, s.settlement_date, s.gross_amount
            FROM settlement_payments sp
            JOIN settlements s ON s.settlement_id = sp.settlement_id
            WHERE sp.payment_id = %s
            """,
            (payment_id,),
        )
