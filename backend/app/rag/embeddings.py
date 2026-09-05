from __future__ import annotations

import os
from typing import Any, List, Optional
from backend.app.core.logging import get_logger

# Restrict thread allocation in containerized environments (Render 512MB RAM)
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

logger = get_logger(__name__)


class EmbeddingService:
    """Generate embeddings using sentence-transformers with lazy loading."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model: Optional[Any] = None

    @property
    def model(self) -> Any:
        """Lazy load the embedding model only when requested."""
        if self._model is None:
            import gc
            gc.collect()
            try:
                import torch
                torch.set_num_threads(1)
            except Exception:
                pass
            logger.info("Loading embedding model: %s", self.model_name)
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name, device="cpu")
            logger.info("Embedding model loaded successfully")
        return self._model


    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """Generate embedding for a search query."""
        return self.embed_text(query)
