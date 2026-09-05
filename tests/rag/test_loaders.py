"""Tests for RAG document loaders."""

from __future__ import annotations

import pytest
from pathlib import Path
from backend.app.rag.config import RAGConfig
from backend.app.rag.loaders import DocumentLoader, DocumentLoadError


@pytest.fixture
def temp_docs_dir(tmp_path):
    """Create a temporary directory with test documents."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    # Create a test markdown file
    md_file = docs_dir / "test.md"
    md_file.write_text("# Test Document\n\nThis is a test content.\n\n## Section 2\nMore content here.")

    # Create a test text file
    txt_file = docs_dir / "test.txt"
    txt_file.write_text("Plain text content.")

    # Create a file that should be excluded
    env_file = docs_dir / ".env"
    env_file.write_text("SECRET=123")

    return docs_dir


@pytest.fixture
def rag_config(temp_docs_dir):
    """Create RAG config for testing."""
    return RAGConfig(
        documents_path=temp_docs_dir,
        vector_db_path=temp_docs_dir / "vector_db",
        chunk_size=100,
        chunk_overlap=10,
        top_k=3,
        embedding_model="test-model",
    )


def test_load_markdown_file(rag_config, temp_docs_dir):
    """Test loading a markdown file."""
    loader = DocumentLoader(rag_config)
    md_file = temp_docs_dir / "test.md"

    result = loader.load_file(md_file)

    assert result is not None
    assert "content" in result
    assert "metadata" in result
    assert "Test Document" in result["content"]
    assert result["metadata"]["file_name"] == "test.md"
    assert result["metadata"]["file_type"] == ".md"


def test_load_text_file(rag_config, temp_docs_dir):
    """Test loading a text file."""
    loader = DocumentLoader(rag_config)
    txt_file = temp_docs_dir / "test.txt"

    result = loader.load_file(txt_file)

    assert result is not None
    assert "Plain text content" in result["content"]
    assert result["metadata"]["file_name"] == "test.txt"


def test_load_excluded_file(rag_config, temp_docs_dir):
    """Test that excluded files are not loaded."""
    loader = DocumentLoader(rag_config)
    env_file = temp_docs_dir / ".env"

    # .env files are excluded, but also have unsupported extension
    # The extension check happens first, so we expect that error
    with pytest.raises(DocumentLoadError):
        loader.load_file(env_file)


def test_load_nonexistent_file(rag_config):
    """Test loading a file that doesn't exist."""
    loader = DocumentLoader(rag_config)
    nonexistent = Path("/nonexistent/file.md")

    with pytest.raises(DocumentLoadError, match="not found"):
        loader.load_file(nonexistent)


def test_load_unsupported_extension(rag_config, temp_docs_dir):
    """Test loading a file with unsupported extension."""
    loader = DocumentLoader(rag_config)
    pdf_file = temp_docs_dir / "test.pdf"
    pdf_file.write_text("PDF content")

    with pytest.raises(DocumentLoadError, match="Unsupported file extension"):
        loader.load_file(pdf_file)


def test_load_directory(rag_config, temp_docs_dir):
    """Test loading all documents from a directory."""
    loader = DocumentLoader(rag_config)

    documents = loader.load_directory(temp_docs_dir)

    # Should load md and txt files, but not .env
    assert len(documents) == 2
    file_names = [doc["metadata"]["file_name"] for doc in documents]
    assert "test.md" in file_names
    assert "test.txt" in file_names
    assert ".env" not in file_names


def test_load_empty_directory(rag_config, tmp_path):
    """Test loading from an empty directory."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    loader = DocumentLoader(rag_config)
    documents = loader.load_directory(empty_dir)

    assert len(documents) == 0
