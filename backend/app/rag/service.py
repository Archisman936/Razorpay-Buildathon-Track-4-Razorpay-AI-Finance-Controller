"""RAG service - clean public interface for retrieval."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.core.config import Settings, get_settings
from backend.app.core.logging import get_logger
from backend.app.rag.chunker import DocumentChunker
from backend.app.rag.config import RAGConfig
from backend.app.rag.embeddings import EmbeddingService
from backend.app.rag.loaders import DocumentLoader, DocumentLoadError
from backend.app.rag.retriever import Retriever, RetrievalError
from backend.app.rag.vector_store import VectorStore, VectorStoreError

logger = get_logger(__name__)


class RAGServiceError(Exception):
    """Raised when RAG service operations fail."""


class RAGService:
    """Public interface for RAG operations."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        config: Optional[RAGConfig] = None,
    ):
        self.settings = settings or get_settings()

        # Initialize RAG config
        if config is None:
            config = RAGConfig(
                documents_path=self.settings.rag_documents_path,
                vector_db_path=self.settings.rag_vector_db_path,
                chunk_size=self.settings.rag_chunk_size,
                chunk_overlap=self.settings.rag_chunk_overlap,
                top_k=self.settings.rag_top_k,
                embedding_model=self.settings.rag_embedding_model,
            )

        self.config = config

        # Initialize components
        self.loader = DocumentLoader(config)
        self.chunker = DocumentChunker(config.chunk_size, config.chunk_overlap)
        self.embedding_service = EmbeddingService(config.embedding_model)
        self.vector_store = VectorStore(config.vector_db_path)
        self.retriever = Retriever(
            embedding_service=self.embedding_service,
            vector_store=self.vector_store,
            top_k=config.top_k,
        )

    def retrieve(self, query: str) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks for a query."""
        try:
            return self.retriever.retrieve(query)
        except RetrievalError as e:
            raise RAGServiceError(f"Retrieval failed: {e}") from e

    def retrieve_with_metadata(self, query: str) -> Dict[str, Any]:
        """Retrieve chunks with structured metadata."""
        try:
            return self.retriever.retrieve_with_metadata(query)
        except RetrievalError as e:
            raise RAGServiceError(f"Retrieval with metadata failed: {e}") from e

    def search(self, query: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search with optional custom top_k."""
        original_top_k = self.retriever.top_k
        if top_k is not None:
            self.retriever.top_k = top_k

        try:
            return self.retrieve(query)
        finally:
            self.retriever.top_k = original_top_k

    def ingest_documents(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """Ingest documents from the configured path into the vector store."""
        try:
            if force_rebuild:
                logger.info("Force rebuild: clearing existing vector store")
                self.vector_store.clear()

            # Load documents
            logger.info("Loading documents from: %s", self.config.documents_path)
            documents = self.loader.load_directory(self.config.documents_path)
            logger.info("Loaded %d documents", len(documents))

            if not documents:
                return {
                    "status": "no_documents",
                    "documents_loaded": 0,
                    "chunks_created": 0,
                    "message": "No documents found to ingest",
                }

            # Chunk documents
            all_chunks = []
            for doc in documents:
                chunks = self.chunker.chunk_document(doc)
                all_chunks.extend(chunks)

            logger.info("Created %d chunks from %d documents", len(all_chunks), len(documents))

            if not all_chunks:
                return {
                    "status": "no_chunks",
                    "documents_loaded": len(documents),
                    "chunks_created": 0,
                    "message": "No chunks created from documents",
                }

            # Generate embeddings
            logger.info("Generating embeddings for %d chunks", len(all_chunks))
            texts = [chunk.content for chunk in all_chunks]
            embeddings = self.embedding_service.embed_texts(texts)
            logger.info("Generated embeddings")

            # Add to vector store
            self.vector_store.add_chunks(all_chunks, embeddings)

            return {
                "status": "success",
                "documents_loaded": len(documents),
                "chunks_created": len(all_chunks),
                "vector_store_count": self.vector_store.count(),
                "message": f"Successfully ingested {len(documents)} documents into {len(all_chunks)} chunks",
            }

        except DocumentLoadError as e:
            raise RAGServiceError(f"Document loading failed: {e}") from e
        except VectorStoreError as e:
            raise RAGServiceError(f"Vector store operation failed: {e}") from e
        except Exception as e:
            raise RAGServiceError(f"Document ingestion failed: {e}") from e

    def health_check(self) -> Dict[str, Any]:
        """Check the health of the RAG system."""
        vector_store_health = self.vector_store.health_check()

        return {
            "ok": vector_store_health.get("ok", True),
            "rag_service": "ok",
            "vector_store": vector_store_health,
            "config": {
                "documents_path": str(self.config.documents_path),
                "vector_db_path": str(self.config.vector_db_path),
                "chunk_size": self.config.chunk_size,
                "chunk_overlap": self.config.chunk_overlap,
                "top_k": self.config.top_k,
                "embedding_model": self.config.embedding_model,
            },
        }


def get_rag_service(settings: Optional[Settings] = None) -> RAGService:
    """Factory function to get RAG service instance."""
    return RAGService(settings=settings)
