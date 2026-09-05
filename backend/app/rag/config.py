"""RAG configuration constants."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class RAGConfig:
    """Configuration for RAG system."""

    documents_path: Path
    vector_db_path: Path
    chunk_size: int
    chunk_overlap: int
    top_k: int
    embedding_model: str

    # Document types to ingest
    allowed_extensions: list[str] | None = None
    excluded_files: list[str] | None = None

    def __post_init__(self):
        if self.allowed_extensions is None:
            self.allowed_extensions = [".md", ".txt", ".rst"]
        if self.excluded_files is None:
            self.excluded_files = [
                ".env",
                ".env.example",
                ".gitignore",
                ".secret",
                "__pycache__",
                ".pyc",
                ".env.local",
                ".env.*",
            ]
