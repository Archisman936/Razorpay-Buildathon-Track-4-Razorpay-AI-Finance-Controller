"""Read-only access to persisted reconciliation cases if a table exists later.

This repository does not write to operational financial tables.
"""

from __future__ import annotations

from backend.app.database.connection import fetch_one


class ReconciliationRepository:
    def get_case(self, case_id: str) -> dict | None:
        """Placeholder: no reconciliation_cases table in the current schema."""
        _ = case_id
        return fetch_one("SELECT NULL AS case_id WHERE FALSE")
