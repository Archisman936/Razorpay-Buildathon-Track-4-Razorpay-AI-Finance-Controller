from __future__ import annotations

from backend.app.database.connection import fetch_all, fetch_one


class SettlementRepository:
    def get_by_id(self, settlement_id: str) -> dict | None:
        return fetch_one(
            "SELECT * FROM settlements WHERE settlement_id = %s",
            (settlement_id,),
        )

    def get_by_utr(self, utr: str) -> dict | None:
        return fetch_one(
            "SELECT * FROM settlements WHERE utr = %s",
            (utr,),
        )

    def list_for_merchant_window(
        self,
        merchant_id: str,
        center_date,
        window_days: int,
        limit: int = 50,
    ) -> list[dict]:
        return fetch_all(
            """
            SELECT * FROM settlements
            WHERE merchant_id = %s
              AND settlement_date IS NOT NULL
              AND ABS((CAST(settlement_date AS date) - %s::date)) <= %s
            ORDER BY settlement_date
            LIMIT %s
            """,
            (merchant_id, center_date, window_days, limit),
        )

    def list_by_merchant(self, merchant_id: str, limit: int = 200) -> list[dict]:
        return fetch_all(
            """
            SELECT * FROM settlements
            WHERE merchant_id = %s
            ORDER BY settlement_date
            LIMIT %s
            """,
            (merchant_id, limit),
        )
