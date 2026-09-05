"""Tests for RAG retriever."""

from __future__ import annotations

import pytest
from unittest.mock import Mock
from pathlib import Path
from backend.app.rag.embeddings import EmbeddingService
from backend.app.rag.vector_store import VectorStore
from backend.app.rag.retriever import Retriever, RetrievalError


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service."""
    service = Mock(spec=EmbeddingService)
    service.embed_query = Mock(return_value=[0.1, 0.2, 0.3] * 128)  # 384 dimensions
    return service


@pytest.fixture
def mock_vector_store():
    """Mock vector store."""
    store = Mock(spec=VectorStore)
    store.search = Mock(return_value=[
        {
            "chunk_id": "chunk_1",
            "content": "Test content about reconciliation",
            "metadata": {"source": "test.md"},
            "score": 0.95,
        },
        {
            "chunk_id": "chunk_2",
            "content": "Test content about settlements",
            "metadata": {"source": "test.md"},
            "score": 0.87,
        },
    ])
    return store


@pytest.fixture
def retriever(mock_embedding_service, mock_vector_store):
    """Create a retriever instance for testing."""
    return Retriever(
        embedding_service=mock_embedding_service,
        vector_store=mock_vector_store,
        top_k=5,
    )


def test_retriever_initialization(retriever, mock_embedding_service, mock_vector_store):
    """Test retriever initialization."""
    assert retriever.embedding_service == mock_embedding_service
    assert retriever.vector_store == mock_vector_store
    assert retriever.top_k == 5


def test_retrieve(retriever, mock_embedding_service, mock_vector_store):
    """Test retrieving chunks for a query."""
    query = "What is settlement reconciliation?"
    
    results = retriever.retrieve(query)
    
    assert len(results) == 2
    assert all("chunk_id" in result for result in results)
    assert all("content" in result for result in results)
    assert all("metadata" in result for result in results)
    
    # Verify that embedding service was called
    mock_embedding_service.embed_query.assert_called_once_with(query)
    
    # Verify that vector store was called
    mock_vector_store.search.assert_called_once()


def test_retrieve_with_filters(retriever, mock_embedding_service, mock_vector_store):
    """Test retrieving with metadata filters."""
    query = "What is settlement reconciliation?"
    filters = {"source": "test.md"}
    
    results = retriever.retrieve(query, filters=filters)
    
    # Verify that vector store was called with filters
    mock_vector_store.search.assert_called_once()
    call_args = mock_vector_store.search.call_args
    assert call_args[1]["where"] == filters


def test_retrieve_empty_query(retriever):
    """Test that empty query raises an error."""
    with pytest.raises(RetrievalError, match="cannot be empty"):
        retriever.retrieve("")


def test_retrieve_whitespace_query(retriever):
    """Test that whitespace-only query raises an error."""
    with pytest.raises(RetrievalError, match="cannot be empty"):
        retriever.retrieve("   ")


def test_retrieve_with_metadata(retriever, mock_embedding_service, mock_vector_store):
    """Test retrieve_with_metadata method."""
    query = "What is settlement reconciliation?"
    
    result = retriever.retrieve_with_metadata(query)
    
    assert "query" in result
    assert "results" in result
    assert "count" in result
    assert "top_k" in result
    assert result["query"] == query
    assert result["count"] == len(result["results"])
    assert result["top_k"] == retriever.top_k


def test_retrieve_with_metadata_error_handling(retriever, mock_embedding_service):
    """Test retrieve_with_metadata error handling."""
    mock_embedding_service.embed_query.side_effect = Exception("Embedding error")
    
    result = retriever.retrieve_with_metadata("test query")
    
    assert result["query"] == "test query"
    assert result["results"] == []
    assert result["count"] == 0
    assert "error" in result


def test_retrieve_top_k_adjustment(retriever, mock_embedding_service, mock_vector_store):
    """Test that top_k can be adjusted dynamically."""
    # Test with default top_k
    retriever.retrieve("test query")
    assert mock_vector_store.search.call_args[1]["top_k"] == 5
    
    # Change top_k
    retriever.top_k = 3
    retriever.retrieve("test query")
    assert mock_vector_store.search.call_args[1]["top_k"] == 3


def test_retrieve_vector_store_error(retriever, mock_embedding_service, mock_vector_store):
    """Test handling of vector store errors."""
    from backend.app.rag.vector_store import VectorStoreError
    mock_vector_store.search.side_effect = VectorStoreError("Search failed")
    
    with pytest.raises(RetrievalError, match="Vector store error"):
        retriever.retrieve("test query")


def test_retrieve_embedding_error(retriever, mock_embedding_service):
    """Test handling of embedding errors."""
    mock_embedding_service.embed_query.side_effect = Exception("Embedding failed")
    
    with pytest.raises(RetrievalError, match="Failed to retrieve chunks"):
        retriever.retrieve("test query")