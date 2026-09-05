from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.app.core.logging import get_logger
from backend.app.rag.chunker import Chunk

logger = get_logger(__name__)


class VectorStoreError(Exception):
    """Raised when vector store operations fail."""


class VectorStore:
    """ChromaDB-based vector store for RAG."""

    def __init__(self, persist_directory: Path, collection_name: str = "rag_documents"):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self._client: Optional[Any] = None
        self._collection: Optional[Any] = None

    @property
    def client(self) -> Any:
        """Lazy load ChromaDB client."""
        if self._client is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            self.persist_directory.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )
            logger.info("ChromaDB client initialized at %s", self.persist_directory)
        return self._client

    @property
    def collection(self) -> Any:
        """Get or create the collection."""
        if self._collection is None:
            try:
                self._collection = self.client.get_collection(name=self.collection_name)
                logger.info("Using existing collection: %s", self.collection_name)
            except Exception:
                self._collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "RAG documents for reconciliation system"},
                )
                logger.info("Created new collection: %s", self.collection_name)
        return self._collection


    def add_chunks(self, chunks: List[Chunk], embeddings: List[List[float]]) -> None:
        """Add chunks with their embeddings to the vector store."""
        if not chunks:
            logger.warning("No chunks to add to vector store")
            return

        if len(chunks) != len(embeddings):
            raise VectorStoreError(
                f"Number of chunks ({len(chunks)}) must match number of embeddings ({len(embeddings)})"
            )

        ids = [chunk.chunk_id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]

        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
            logger.info("Added %d chunks to vector store", len(chunks))
        except Exception as e:
            raise VectorStoreError(f"Failed to add chunks to vector store: {e}") from e

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar chunks using query embedding."""
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
            )

            if not results or not results["ids"]:
                return []

            formatted_results = []
            for i in range(len(results["ids"][0])):
                formatted_results.append(
                    {
                        "chunk_id": results["ids"][0][i],
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "score": results["distances"][0][i] if "distances" in results else None,
                    }
                )

            return formatted_results

        except Exception as e:
            raise VectorStoreError(f"Failed to search vector store: {e}") from e

    def count(self) -> int:
        """Get the total number of chunks in the collection."""
        try:
            return self.collection.count()
        except chromadb.errors.NotFoundError:
            # Collection doesn't exist yet
            return 0
        except Exception as e:
            raise VectorStoreError(f"Failed to get collection count: {e}") from e

    def clear(self) -> None:
        """Clear all documents from the collection."""
        try:
            try:
                self.client.delete_collection(name=self.collection_name)
                self._collection = None
                logger.info("Cleared collection: %s", self.collection_name)
            except Exception:
                # Collection doesn't exist or other error, just reset the reference
                self._collection = None
                logger.info("Collection %s reference cleared (may not have existed)", self.collection_name)
        except Exception as e:
            raise VectorStoreError(f"Failed to clear collection: {e}") from e

    def health_check(self) -> Dict[str, Any]:
        """Check the health of the vector store."""
        try:
            count = self.count()
            return {
                "ok": True,
                "collection_name": self.collection_name,
                "document_count": count,
                "persist_directory": str(self.persist_directory),
            }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "collection_name": self.collection_name,
            }
