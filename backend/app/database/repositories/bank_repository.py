from __future__ import annotations

from backend.app.database.connection import fetch_all, fetch_one


class BankRepository:
    def get_by_id(self, bank_record_id: str) -> dict | None:
        return fetch_one(
            "SELECT * FROM bank_records WHERE bank_record_id = %s",
            (bank_record_id,),
        )

    def list_by_merchant(self, merchant_id: str, limit: int = 200) -> list[dict]:
        return fetch_all(
            """
            SELECT * FROM bank_records
            WHERE merchant_id = %s
            ORDER BY transaction_date
            LIMIT %s
            """,
            (merchant_id, limit),
        )
