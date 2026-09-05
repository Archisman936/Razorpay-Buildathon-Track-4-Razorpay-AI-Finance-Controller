"""Lookups for remaining operational entities used by deterministic rules."""

from __future__ import annotations

from backend.app.database.connection import fetch_all, fetch_one


class EntityRepository:
    def get_invoice(self, invoice_id: str) -> dict | None:
        return fetch_one(
            "SELECT * FROM invoices WHERE invoice_id = %s",
            (invoice_id,),
        )

    def list_invoices_for_order(self, order_id: str) -> list[dict]:
        return fetch_all(
            "SELECT * FROM invoices WHERE order_id = %s",
            (order_id,),
        )

    def list_gst_for_invoice(self, invoice_id: str) -> list[dict]:
        return fetch_all(
            "SELECT * FROM gst_records WHERE invoice_id = %s",
            (invoice_id,),
        )

    def list_adjustments_for_settlement(self, settlement_id: str) -> list[dict]:
        return fetch_all(
            "SELECT * FROM adjustments WHERE settlement_id = %s",
            (settlement_id,),
        )

    def list_books_for_reference(self, reference_id: str) -> list[dict]:
        return fetch_all(
            "SELECT * FROM books WHERE reference_id = %s OR canonical_reference_id = %s",
            (reference_id, reference_id),
        )
