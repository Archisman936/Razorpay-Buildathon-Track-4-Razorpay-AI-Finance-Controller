"""Database initialization and schema migration helpers."""

from pathlib import Path
import psycopg2
from backend.app.core.config import Settings, get_settings
from backend.app.core.logging import get_logger
from backend.app.database.connection import get_connection

logger = get_logger(__name__)


def ensure_database_initialized(settings: Settings | None = None) -> dict:
    """
    Checks whether the database tables exist.
    If 'merchants' does not exist, executes database/schema/schema.sql
    and loads canonical seed data from data/normalized/.
    """
    settings = settings or get_settings()

    # 1. Check if merchants table exists
    try:
        with get_connection(settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'merchants'"
                )
                if cur.fetchone():
                    cur.execute("SELECT COUNT(*) FROM merchants")
                    count = cur.fetchone()[0]
                    if count > 0:
                        logger.info("Database already initialized (%d merchants present).", count)
                        return {
                            "ok": True,
                            "initialized": False,
                            "message": f"Database already initialized ({count} merchants present).",
                            "merchants": count,
                        }
    except Exception as e:
        logger.warning("Database inspection error: %s", e)
        # If connection fails completely, report it
        if "does not exist" not in str(e).lower() and "relation" not in str(e).lower():
            return {"ok": False, "error": f"Cannot connect to database: {e}"}

    # 2. Apply schema.sql
    logger.info("Applying database schema from schema.sql...")
    schema_file = Path(settings.project_root) / "database" / "schema" / "schema.sql"
    if not schema_file.exists():
        logger.error("schema.sql not found at %s", schema_file)
        return {"ok": False, "error": f"schema.sql not found at {schema_file}"}

    try:
        schema_sql = schema_file.read_text(encoding="utf-8")
        with get_connection(settings) as conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
            conn.commit()
        logger.info("Schema applied successfully.")
    except Exception as e:
        logger.error("Failed to apply schema.sql: %s", e)
        return {"ok": False, "error": f"Schema application failed: {e}"}

    # 3. Seed canonical data from data/normalized/
    normalized_dir = Path(settings.project_root) / "data" / "normalized"
    if not normalized_dir.exists():
        logger.warning("Normalized data directory %s does not exist; skipping seed.", normalized_dir)
        return {
            "ok": True,
            "initialized": True,
            "message": "Schema applied, but seed data directory was not found.",
        }

    logger.info("Seeding canonical data from %s...", normalized_dir)
    try:
        from scripts import load_canonical
        load_canonical.main(truncate_first=False)
        logger.info("Canonical seed data loaded successfully.")
        return {
            "ok": True,
            "initialized": True,
            "message": "Database schema created and canonical seed data loaded successfully.",
        }
    except Exception as e:
        logger.error("Seed data loading error: %s", e)
        return {
            "ok": True,
            "initialized": True,
            "warning": f"Schema applied, but seeding encountered: {e}",
        }
