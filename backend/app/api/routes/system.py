"""System maintenance and database lifecycle endpoints."""

from fastapi import APIRouter, Depends
from backend.app.api.dependencies import get_app_settings
from backend.app.core.config import Settings
from backend.app.database.init_db import ensure_database_initialized
from backend.app.database.connection import get_connection

router = APIRouter(prefix="/system", tags=["system"])


@router.post("/init-db")
def init_database(settings: Settings = Depends(get_app_settings)) -> dict:
    """
    Initializes PostgreSQL tables from schema.sql and seeds canonical data.
    Safe to call repeatedly (idempotent).
    """
    return ensure_database_initialized(settings)


@router.get("/db-summary")
def get_db_summary(settings: Settings = Depends(get_app_settings)) -> dict:
    """Returns row counts for all core financial tables."""
    tables = [
        "merchants", "customers", "orders", "invoices", "payments",
        "fees", "refunds", "settlements", "settlement_payments",
        "bank_records", "books", "gst_records", "adjustments"
    ]
    summary = {}
    try:
        with get_connection(settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
                existing = {row[0] for row in cur.fetchall()}
                for t in tables:
                    if t in existing:
                        cur.execute(f"SELECT COUNT(*) FROM {t}")
                        summary[t] = cur.fetchone()[0]
                    else:
                        summary[t] = 0
        return {"ok": True, "tables": summary, "total_rows": sum(summary.values())}
    except Exception as e:
        return {"ok": False, "error": str(e)}
