"""PostgreSQL connection helpers. Credentials come from environment only."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.extras import RealDictCursor

from backend.app.core.config import Settings, get_settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class DatabaseConfigError(RuntimeError):
    pass


def _require_credentials(settings: Settings) -> None:
    if settings.database_url:
        return
    if not settings.db_password:
        raise DatabaseConfigError(
            "PostgreSQL password is not configured. Set POSTGRES_PASSWORD or DATABASE_URL."
        )


@contextmanager
def get_connection(settings: Settings | None = None) -> Iterator:
    settings = settings or get_settings()
    _require_credentials(settings)
    conn = psycopg2.connect(**settings.postgres_kwargs())
    try:
        yield conn
    finally:
        conn.close()


def ping_database(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    try:
        _require_credentials(settings)
        with get_connection(settings) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return {"ok": True, "database": settings.db_name}
    except Exception as exc:
        logger.warning("database ping failed: %s", exc)
        return {"ok": False, "error": str(exc), "database": settings.db_name}


def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None


def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
