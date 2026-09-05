"""Tests for RAG document chunker."""

from __future__ import annotations

import pytest
from backend.app.rag.chunker import DocumentChunker, Chunk


@pytest.fixture
def chunker():
    """Create a chunker instance for testing."""
    return DocumentChunker(chunk_size=100, chunk_overlap=20)


def test_chunk_simple_document(chunker):
    """Test chunking a simple document."""
    document = {
        "content": "This is a simple test document with some text that should be chunked.",
        "metadata": {"source": "test.txt"},
    }

    chunks = chunker.chunk_document(document)

    assert len(chunks) > 0
    assert all(isinstance(chunk, Chunk) for chunk in chunks)
    assert all(chunk.chunk_id for chunk in chunks)
    assert all(chunk.content for chunk in chunks)


def test_chunk_preserves_metadata(chunker):
    """Test that chunking preserves document metadata."""
    document = {
        "content": "Test content for metadata preservation.",
        "metadata": {"source": "test.md", "author": "test"},
    }

    chunks = chunker.chunk_document(document)

    for chunk in chunks:
        assert chunk.metadata["source"] == "test.md"
        assert chunk.metadata["author"] == "test"


def test_chunk_with_headers(chunker):
    """Test chunking with markdown headers."""
    document = {
        "content": "# Header 1\nContent under header 1.\n\n## Header 2\nContent under header 2.",
        "metadata": {"source": "test.md"},
    }

    chunks = chunker.chunk_document(document)

    # Should preserve section information
    assert len(chunks) > 0
    # The chunker should split the document, and chunks should have content
    assert all(chunk.content for chunk in chunks)
    # All chunks should preserve the original metadata
    assert all(chunk.metadata["source"] == "test.md" for chunk in chunks)


def test_chunk_large_document(chunker):
    """Test chunking a large document."""
    large_content = "This is a test sentence. " * 50  # Create large content
    document = {
        "content": large_content,
        "metadata": {"source": "large.txt"},
    }

    chunks = chunker.chunk_document(document)

    assert len(chunks) > 1  # Should be split into multiple chunks
    # Check that chunks overlap
    if len(chunks) > 1:
        # Overlap check: end of chunk i should overlap with start of chunk i+1
        for i in range(len(chunks) - 1):
            chunk_end = chunks[i].content[-20:]
            chunk_start = chunks[i + 1].content[:20]
            # They should share some content due to overlap
            overlap = set(chunk_end.split()) & set(chunk_start.split())
            assert len(overlap) > 0


def test_chunk_empty_document(chunker):
    """Test chunking an empty document."""
    document = {
        "content": "",
        "metadata": {"source": "empty.txt"},
    }

    chunks = chunker.chunk_document(document)

    # Should handle empty content gracefully
    assert len(chunks) == 0


def test_chunk_indices(chunker):
    """Test that chunks have correct indices."""
    document = {
        "content": "Test content for indices. " * 10,
        "metadata": {"source": "test.txt"},
    }

    chunks = chunker.chunk_document(document)

    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i


def test_chunk_size_limits(chunker):
    """Test that chunks respect size limits."""
    large_content = "Word " * 200
    document = {
        "content": large_content,
        "metadata": {"source": "test.txt"},
    }

    chunks = chunker.chunk_document(document)

    for chunk in chunks:
        # Allow some tolerance for sentence boundaries
        assert len(chunk.content) <= chunker.chunk_size + 50
