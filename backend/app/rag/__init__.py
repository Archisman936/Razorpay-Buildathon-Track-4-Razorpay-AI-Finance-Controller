"""RAG module for document retrieval and knowledge base."""

from backend.app.rag.service import RAGService, RAGServiceError, get_rag_service

__all__ = ["RAGService", "RAGServiceError", "get_rag_service"]
