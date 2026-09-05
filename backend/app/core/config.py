"""Environment-driven runtime configuration."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def _project_root() -> Path:
    """razorpay-ai-finance-controller/ (backend/app/core/config.py → parents[3])."""
    return Path(__file__).resolve().parents[3]


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


class Settings:
    """Paths and connection settings. No machine-specific absolute defaults."""

    def __init__(self) -> None:
        if load_dotenv is not None:
            load_dotenv(_project_root() / ".env", override=False)
        self.project_root = Path(_env("PROJECT_ROOT", str(_project_root())))

        self.db_host = _env("POSTGRES_HOST", "localhost")
        self.db_port = int(_env("POSTGRES_PORT", "5432"))
        self.db_name = _env("POSTGRES_DB", "razorpay_recon")
        self.db_user = _env("POSTGRES_USER", "postgres")
        self.db_password = _env("POSTGRES_PASSWORD", "")
        self.database_url = _env("DATABASE_URL")

        ml_root = Path(
            _env(
                "ML_MODELS_DIR",
                str(self.project_root / "tools" / "ML_Models"),
            )
        )
        self.ml_models_dir = ml_root
        self.reconciliation_model_dir = Path(
            _env(
                "RECONCILIATION_MODEL_DIR",
                str(ml_root / "Reconciliation Model"),
            )
        )
        self.exception_model_dir = Path(
            _env(
                "EXCEPTION_MODEL_DIR",
                str(ml_root / "Exception Classification"),
            )
        )
        self.reconciliation_model_filename = _env(
            "RECONCILIATION_MODEL_FILENAME",
            "best_reconciliation_model.joblib",
        )
        self.exception_model_filename = _env(
            "EXCEPTION_MODEL_FILENAME",
            "best_exception_classifier.joblib",
        )

        self.candidate_window_days = int(_env("CANDIDATE_WINDOW_DAYS", "25"))
        self.max_candidates = int(_env("MAX_CANDIDATES", "20"))
        self.amount_exact_tolerance = float(_env("AMOUNT_EXACT_TOLERANCE", "0.01"))
        self.ambiguity_margin = float(_env("ML_AMBIGUITY_MARGIN", "0.08"))
        self.log_level = _env("LOG_LEVEL", "INFO")

        # LLM Configuration
        self.gemini_api_key = _env("GEMINI_API_KEY", "")
        self.gemini_model = _env("GEMINI_MODEL", "gemini-3.6-flash")


        # RAG Configuration
        self.rag_documents_path = Path(
            _env("RAG_DOCUMENTS_PATH", str(self.project_root / "docs"))
        )
        self.rag_vector_db_path = Path(
            _env("RAG_VECTOR_DB_PATH", str(self.project_root / "data" / "rag_vector_db"))
        )
        self.rag_chunk_size = int(_env("RAG_CHUNK_SIZE", "500"))
        self.rag_chunk_overlap = int(_env("RAG_CHUNK_OVERLAP", "50"))
        self.rag_top_k = int(_env("RAG_TOP_K", "5"))
        self.rag_embedding_model = _env("RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    @property
    def reconciliation_model_path(self) -> Path:
        return self.reconciliation_model_dir / self.reconciliation_model_filename

    @property
    def exception_model_path(self) -> Path:
        return self.exception_model_dir / self.exception_model_filename

    @property
    def reconciliation_schema_path(self) -> Path:
        return self.reconciliation_model_dir / "feature_schema.json"

    @property
    def exception_schema_path(self) -> Path:
        return self.exception_model_dir / "feature_schema.json"

    def postgres_kwargs(self) -> dict:
        if self.database_url:
            return {"dsn": self.database_url}
        return {
            "host": self.db_host,
            "port": self.db_port,
            "dbname": self.db_name,
            "user": self.db_user,
            "password": self.db_password,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
