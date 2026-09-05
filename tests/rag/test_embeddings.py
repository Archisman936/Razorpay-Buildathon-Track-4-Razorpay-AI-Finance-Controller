"""Tests for RAG embedding service."""

from __future__ import annotations

import pytest
from backend.app.rag.embeddings import EmbeddingService


@pytest.fixture
def embedding_service():
    """Create an embedding service instance for testing."""
    return EmbeddingService(model_name="all-MiniLM-L6-v2")


def test_embed_text(embedding_service):
    """Test embedding a single text."""
    text = "This is a test sentence for embedding."
    
    embedding = embedding_service.embed_text(text)
    
    assert isinstance(embedding, list)
    assert len(embedding) > 0
    assert all(isinstance(x, float) for x in embedding)


def test_embed_texts(embedding_service):
    """Test embedding multiple texts."""
    texts = [
        "First test sentence.",
        "Second test sentence.",
        "Third test sentence.",
    ]
    
    embeddings = embedding_service.embed_texts(texts)
    
    assert isinstance(embeddings, list)
    assert len(embeddings) == len(texts)
    assert all(isinstance(emb, list) for emb in embeddings)
    assert all(len(emb) > 0 for emb in embeddings)


def test_embed_query(embedding_service):
    """Test embedding a query."""
    query = "What is settlement reconciliation?"
    
    embedding = embedding_service.embed_query(query)
    
    assert isinstance(embedding, list)
    assert len(embedding) > 0
    assert all(isinstance(x, float) for x in embedding)


def test_embed_empty_text(embedding_service):
    """Test that empty text raises an error."""
    with pytest.raises(ValueError, match="cannot be empty"):
        embedding_service.embed_text("")


def test_embed_texts_empty_list(embedding_service):
    """Test that empty list returns empty list."""
    embeddings = embedding_service.embed_texts([])
    
    assert embeddings == []


def test_embedding_consistency(embedding_service):
    """Test that the same text produces the same embedding."""
    text = "Consistency test sentence."
    
    embedding1 = embedding_service.embed_text(text)
    embedding2 = embedding_service.embed_text(text)
    
    assert embedding1 == embedding2


def test_embedding_differentiation(embedding_service):
    """Test that different texts produce different embeddings."""
    text1 = "First unique sentence."
    text2 = "Second unique sentence."
    
    embedding1 = embedding_service.embed_text(text1)
    embedding2 = embedding_service.embed_text(text2)
    
    # Embeddings should be different
    assert embedding1 != embedding2