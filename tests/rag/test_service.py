"""Tests for RAG service."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from backend.app.rag.service import RAGService, RAGServiceError
from backend.app.rag.config import RAGConfig


@pytest.fixture
def temp_rag_dirs(tmp_path):
    """Create temporary directories for RAG."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    
    # Create test documents
    (docs_dir / "test1.md").write_text("# Test Document 1\n\nContent about reconciliation.")
    (docs_dir / "test2.txt").write_text("Content about settlements.")
    
    vector_db_path = tmp_path / "vector_db"
    
    return docs_dir, vector_db_path


@pytest.fixture
def rag_config(temp_rag_dirs):
    """Create RAG config for testing."""
    docs_dir, vector_db_path = temp_rag_dirs
    return RAGConfig(
        documents_path=docs_dir,
        vector_db_path=vector_db_path,
        chunk_size=100,
        chunk_overlap=10,
        top_k=3,
        embedding_model="all-MiniLM-L6-v2",
    )


@pytest.fixture
def mock_settings(rag_config):
    """Mock settings for testing."""
    settings = Mock()
    settings.rag_documents_path = rag_config.documents_path
    settings.rag_vector_db_path = rag_config.vector_db_path
    settings.rag_chunk_size = rag_config.chunk_size
    settings.rag_chunk_overlap = rag_config.chunk_overlap
    settings.rag_top_k = rag_config.top_k
    settings.rag_embedding_model = rag_config.embedding_model
    return settings


@pytest.fixture
def rag_service(mock_settings):
    """Create a RAG service instance for testing."""
    return RAGService(settings=mock_settings)


def test_rag_service_initialization(rag_service, mock_settings):
    """Test RAG service initialization."""
    assert rag_service.settings == mock_settings
    assert rag_service.config.documents_path == mock_settings.rag_documents_path
    assert rag_service.config.vector_db_path == mock_settings.rag_vector_db_path


def test_rag_service_component_initialization(rag_service):
    """Test that all components are initialized."""
    assert rag_service.loader is not None
    assert rag_service.chunker is not None
    assert rag_service.embedding_service is not None
    assert rag_service.vector_store is not None
    assert rag_service.retriever is not None


def test_retrieve(rag_service):
    """Test retrieving documents."""
    # Mock the retriever
    rag_service.retriever.retrieve = Mock(return_value=[
        {
            "chunk_id": "chunk_1",
            "content": "Test content",
            "metadata": {"source": "test.md"},
            "score": 0.95,
        }
    ])
    
    results = rag_service.retrieve("test query")
    
    assert len(results) == 1
    assert results[0]["content"] == "Test content"
    rag_service.retriever.retrieve.assert_called_once_with("test query")


def test_retrieve_with_metadata(rag_service):
    """Test retrieve_with_metadata method."""
    # Mock the retriever
    rag_service.retriever.retrieve_with_metadata = Mock(return_value={
        "query": "test query",
        "results": [],
        "count": 0,
        "top_k": 3,
    })
    
    result = rag_service.retrieve_with_metadata("test query")
    
    assert result["query"] == "test query"
    assert result["count"] == 0
    rag_service.retriever.retrieve_with_metadata.assert_called_once()


def test_search_with_custom_top_k(rag_service):
    """Test search with custom top_k."""
    # Mock the retriever
    rag_service.retriever.retrieve = Mock(return_value=[])
    
    original_top_k = rag_service.retriever.top_k
    rag_service.search("test query", top_k=10)
    
    # Verify top_k was temporarily changed
    assert rag_service.retriever.top_k == original_top_k  # Should be restored


def test_ingest_documents(rag_service):
    """Test document ingestion."""
    # Mock the components
    rag_service.loader.load_directory = Mock(return_value=[
        {"content": "Test content", "metadata": {"source": "test.md"}}
    ])
    rag_service.chunker.chunk_document = Mock(return_value=[
        Mock(chunk_id="chunk_1", content="Chunk content", metadata={}, chunk_index=0)
    ])
    rag_service.embedding_service.embed_texts = Mock(return_value=[[0.1, 0.2, 0.3]])
    rag_service.vector_store.add_chunks = Mock()
    rag_service.vector_store.count = Mock(return_value=1)

    result = rag_service.ingest_documents()

    assert result["status"] == "success"
    assert result["documents_loaded"] == 1
    assert result["chunks_created"] == 1
    rag_service.loader.load_directory.assert_called_once()
    rag_service.embedding_service.embed_texts.assert_called_once()
    rag_service.vector_store.add_chunks.assert_called_once()


def test_ingest_documents_force_rebuild(rag_service):
    """Test document ingestion with force rebuild."""
    # Mock the components
    rag_service.vector_store.clear = Mock()
    rag_service.loader.load_directory = Mock(return_value=[])
    
    rag_service.ingest_documents(force_rebuild=True)
    
    rag_service.vector_store.clear.assert_called_once()


def test_ingest_documents_no_documents(rag_service):
    """Test ingestion when no documents are found."""
    rag_service.loader.load_directory = Mock(return_value=[])
    
    result = rag_service.ingest_documents()
    
    assert result["status"] == "no_documents"
    assert result["documents_loaded"] == 0
    assert result["chunks_created"] == 0


def test_ingest_documents_no_chunks(rag_service):
    """Test ingestion when no chunks are created."""
    rag_service.loader.load_directory = Mock(return_value=[
        {"content": "Test", "metadata": {}}
    ])
    rag_service.chunker.chunk_document = Mock(return_value=[])
    
    result = rag_service.ingest_documents()
    
    assert result["status"] == "no_chunks"
    assert result["documents_loaded"] == 1
    assert result["chunks_created"] == 0


def test_health_check(rag_service):
    """Test health check."""
    rag_service.vector_store.health_check = Mock(return_value={
        "ok": True,
        "document_count": 10,
    })
    
    health = rag_service.health_check()
    
    assert health["rag_service"] == "ok"
    assert "vector_store" in health
    assert "config" in health
    assert health["vector_store"]["ok"] is True


def test_retrieve_error_handling(rag_service):
    """Test error handling in retrieve."""
    from backend.app.rag.retriever import RetrievalError
    rag_service.retriever.retrieve = Mock(side_effect=RetrievalError("Retrieval failed"))
    
    with pytest.raises(RAGServiceError, match="Retrieval failed"):
        rag_service.retrieve("test query")


def test_ingest_documents_loading_error(rag_service):
    """Test ingestion error handling for document loading."""
    from backend.app.rag.loaders import DocumentLoadError
    rag_service.loader.load_directory = Mock(side_effect=DocumentLoadError("Load failed"))
    
    with pytest.raises(RAGServiceError, match="Document loading failed"):
        rag_service.ingest_documents()


def test_ingest_documents_vector_store_error(rag_service):
    """Test ingestion error handling for vector store."""
    from backend.app.rag.vector_store import VectorStoreError
    rag_service.loader.load_directory = Mock(return_value=[{"content": "test", "metadata": {}}])
    rag_service.chunker.chunk_document = Mock(return_value=[Mock(chunk_id="c1", content="test", metadata={}, chunk_index=0)])
    rag_service.embedding_service.embed_texts = Mock(return_value=[[0.1]])
    rag_service.vector_store.add_chunks = Mock(side_effect=VectorStoreError("Vector store error"))
    
    with pytest.raises(RAGServiceError, match="Vector store operation failed"):
        rag_service.ingest_documents()


def test_get_rag_service_factory():
    """Test the get_rag_service factory function."""
    from backend.app.rag import get_rag_service
    
    service = get_rag_service()
    
    assert isinstance(service, RAGService)
    assert service.loader is not None
    assert service.chunker is not None
    assert service.embedding_service is not None
    assert service.vector_store is not None
    assert service.retriever is not None