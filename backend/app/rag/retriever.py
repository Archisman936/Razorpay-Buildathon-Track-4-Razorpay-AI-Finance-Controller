"""Retriever for RAG system."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.app.core.logging import get_logger
from backend.app.rag.embeddings import EmbeddingService
from backend.app.rag.vector_store import VectorStore, VectorStoreError

logger = get_logger(__name__)


class RetrievalError(Exception):
    """Raised when retrieval fails."""


class Retriever:
    """Retrieve relevant chunks from the vector store."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        top_k: int = 5,
    ):
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.top_k = top_k

    def retrieve(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks for a query."""
        if not query or not query.strip():
            raise RetrievalError("Query cannot be empty")

        try:
            # Generate query embedding
            query_embedding = self.embedding_service.embed_query(query)

            # Search vector store
            results = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=self.top_k,
                where=filters,
            )

            logger.info("Retrieved %d chunks for query: %s", len(results), query[:50])
            return results

        except Exception as e:
            logger.warning("Vector retrieval failed (%s); using resilient document fallback.", e)
            return self._fallback_keyword_search(query)

    def _fallback_keyword_search(self, query: str) -> List[Dict[str, Any]]:
        """Fallback to scanning docs/ directly to preserve memory and prevent OOM."""
        from pathlib import Path
        import re

        docs_dir = Path(__file__).resolve().parents[3] / "docs"
        if not docs_dir.exists():
            return []

        stopwords = {"the", "a", "an", "is", "of", "and", "in", "to", "what", "how", "why", "are", "for"}
        words = set(re.findall(r"\w+", query.lower())) - stopwords
        matched_chunks = []

        for md_file in docs_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                sections = re.split(r"\n(?=#{1,3}\s)", content)
                for i, sec in enumerate(sections):
                    sec_clean = sec.strip()
                    if not sec_clean:
                        continue
                    score = sum(1 for w in words if w in sec_clean.lower())
                    if score > 0 or not words:
                        matched_chunks.append({
                            "chunk_id": f"{md_file.stem}_{i}",
                            "content": sec_clean[:1200],
                            "metadata": {"source": md_file.name},
                            "score": float(score),
                        })
            except Exception:
                pass

        matched_chunks.sort(key=lambda x: x["score"], reverse=True)
        return matched_chunks[:self.top_k]

    def retrieve_with_metadata(
        self,
        query: str,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Retrieve chunks with structured metadata response."""
        try:
            results = self.retrieve(query, metadata_filters)

            return {
                "query": query,
                "results": results,
                "count": len(results),
                "top_k": self.top_k,
            }

        except RetrievalError as e:
            return {
                "query": query,
                "results": [],
                "count": 0,
                "error": str(e),
            }
