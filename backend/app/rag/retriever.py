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

        except VectorStoreError as e:
            raise RetrievalError(f"Vector store error during retrieval: {e}") from e
        except Exception as e:
            raise RetrievalError(f"Failed to retrieve chunks: {e}") from e

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
