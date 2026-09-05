"""Tests for RAG vector store."""

from __future__ import annotations

import pytest
from pathlib import Path
from backend.app.rag.chunker import Chunk
from backend.app.rag.vector_store import VectorStore, VectorStoreError


@pytest.fixture
def temp_vector_db(tmp_path):
    """Create a temporary directory for vector store."""
    vector_db_path = tmp_path / "vector_db"
    return vector_db_path


@pytest.fixture
def vector_store(temp_vector_db):
    """Create a vector store instance for testing."""
    return VectorStore(persist_directory=temp_vector_db, collection_name="test_collection")


@pytest.fixture
def sample_chunks():
    """Create sample chunks for testing."""
    return [
        Chunk(
            chunk_id="chunk_1",
            content="This is the first test chunk about reconciliation.",
            metadata={"source": "test.md", "section": "Introduction"},
            chunk_index=0,
        ),
        Chunk(
            chunk_id="chunk_2",
            content="This is the second test chunk about settlements.",
            metadata={"source": "test.md", "section": "Settlements"},
            chunk_index=1,
        ),
        Chunk(
            chunk_id="chunk_3",
            content="This is the third test chunk about transactions.",
            metadata={"source": "test.md", "section": "Transactions"},
            chunk_index=2,
        ),
    ]


@pytest.fixture
def sample_embeddings():
    """Create sample embeddings for testing."""
    # Create simple mock embeddings (384 dimensions like all-MiniLM-L6-v2)
    import random
    random.seed(42)
    
    return [[random.random() for _ in range(384)] for _ in range(3)]


def test_vector_store_initialization(vector_store, temp_vector_db):
    """Test vector store initialization."""
    assert vector_store.persist_directory == temp_vector_db
    assert vector_store.collection_name == "test_collection"


def test_vector_store_client_initialization(vector_store):
    """Test that ChromaDB client is initialized."""
    client = vector_store.client
    assert client is not None


def test_vector_store_collection_creation(vector_store):
    """Test that collection is created."""
    collection = vector_store.collection
    assert collection is not None
    assert collection.name == "test_collection"


def test_add_chunks(vector_store, sample_chunks, sample_embeddings):
    """Test adding chunks to vector store."""
    vector_store.add_chunks(sample_chunks, sample_embeddings)
    
    count = vector_store.count()
    assert count == len(sample_chunks)


def test_add_chunks_mismatch_length(vector_store, sample_chunks):
    """Test that adding chunks with mismatched embedding count raises error."""
    wrong_embeddings = [[0.1, 0.2]]  # Only 1 embedding for 3 chunks
    
    with pytest.raises(VectorStoreError, match="must match"):
        vector_store.add_chunks(sample_chunks, wrong_embeddings)


def test_add_empty_chunks(vector_store):
    """Test adding empty chunks list."""
    vector_store.add_chunks([], [])
    
    count = vector_store.count()
    assert count == 0


def test_search(vector_store, sample_chunks, sample_embeddings):
    """Test searching the vector store."""
    # Add chunks first
    vector_store.add_chunks(sample_chunks, sample_embeddings)
    
    # Search with a query embedding
    query_embedding = sample_embeddings[0]
    results = vector_store.search(query_embedding=query_embedding, top_k=2)
    
    assert len(results) <= 2
    assert all("chunk_id" in result for result in results)
    assert all("content" in result for result in results)
    assert all("metadata" in result for result in results)


def test_search_empty_vector_store(vector_store):
    """Test searching empty vector store."""
    query_embedding = [0.1] * 384
    results = vector_store.search(query_embedding=query_embedding, top_k=5)
    
    assert results == []


def test_count(vector_store, sample_chunks, sample_embeddings):
    """Test counting chunks in vector store."""
    # Initially empty
    assert vector_store.count() == 0
    
    # Add chunks
    vector_store.add_chunks(sample_chunks, sample_embeddings)
    assert vector_store.count() == len(sample_chunks)


def test_clear(vector_store, sample_chunks, sample_embeddings):
    """Test clearing the vector store."""
    # Add chunks
    vector_store.add_chunks(sample_chunks, sample_embeddings)
    assert vector_store.count() > 0
    
    # Clear
    vector_store.clear()
    assert vector_store.count() == 0


def test_health_check(vector_store):
    """Test health check."""
    health = vector_store.health_check()
    
    assert "ok" in health
    assert "collection_name" in health
    assert "document_count" in health
    assert health["collection_name"] == "test_collection"


def test_health_check_with_chunks(vector_store, sample_chunks, sample_embeddings):
    """Test health check after adding chunks."""
    vector_store.add_chunks(sample_chunks, sample_embeddings)
    
    health = vector_store.health_check()
    
    assert health["ok"] is True
    assert health["document_count"] == len(sample_chunks)