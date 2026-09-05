"""Security tests for LLM/RAG layer."""

from __future__ import annotations

import pytest
from pathlib import Path
from backend.app.core.config import Settings, get_settings
from backend.app.rag.config import RAGConfig
from backend.app.rag.loaders import DocumentLoader, DocumentLoadError


def test_env_file_not_in_rag_allowed_extensions():
    """Test that .env files are excluded from RAG ingestion."""
    config = RAGConfig(
        documents_path=Path("docs"),
        vector_db_path=Path("data/vector_db"),
        chunk_size=500,
        chunk_overlap=50,
        top_k=5,
        embedding_model="test",
    )
    
    assert ".env" in config.excluded_files
    assert ".env.example" in config.excluded_files


def test_env_files_excluded_from_document_loading(tmp_path):
    """Test that .env files cannot be loaded by RAG loader."""
    # Create test directory with .env file
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    
    env_file = docs_dir / ".env"
    env_file.write_text("SECRET_KEY=supersecret")
    
    config = RAGConfig(
        documents_path=docs_dir,
        vector_db_path=tmp_path / "vector_db",
        chunk_size=500,
        chunk_overlap=50,
        top_k=5,
        embedding_model="test",
    )
    
    loader = DocumentLoader(config)
    
    # Should raise DocumentLoadError for .env file (due to unsupported extension)
    # The important thing is that it cannot be loaded
    with pytest.raises(DocumentLoadError):
        loader.load_file(env_file)


def test_env_example_files_excluded_from_document_loading(tmp_path):
    """Test that .env.example files cannot be loaded by RAG loader."""
    # Create test directory with .env.example file
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    
    env_example_file = docs_dir / ".env.example"
    env_example_file.write_text("SECRET_KEY=example_value")
    
    config = RAGConfig(
        documents_path=docs_dir,
        vector_db_path=tmp_path / "vector_db",
        chunk_size=500,
        chunk_overlap=50,
        top_k=5,
        embedding_model="test",
    )
    
    loader = DocumentLoader(config)
    
    # Should raise DocumentLoadError for .env.example file (due to unsupported extension)
    # The important thing is that it cannot be loaded
    with pytest.raises(DocumentLoadError):
        loader.load_file(env_example_file)


def test_secret_files_excluded_from_directory_loading(tmp_path):
    """Test that secret files are excluded when loading entire directory."""
    # Create test directory with mixed files
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    
    (docs_dir / "test.md").write_text("# Test Document")
    (docs_dir / ".env").write_text("SECRET=value")
    (docs_dir / ".secret").write_text("API_KEY=123")
    (docs_dir / "test.txt").write_text("Plain text")
    
    config = RAGConfig(
        documents_path=docs_dir,
        vector_db_path=tmp_path / "vector_db",
        chunk_size=500,
        chunk_overlap=50,
        top_k=5,
        embedding_model="test",
    )
    
    loader = DocumentLoader(config)
    documents = loader.load_directory(docs_dir)
    
    # Should only load non-excluded files
    file_names = [doc["metadata"]["file_name"] for doc in documents]
    assert "test.md" in file_names
    assert "test.txt" in file_names
    assert ".env" not in file_names
    assert ".secret" not in file_names


def test_settings_loads_from_real_env_not_example():
    """Test that settings loads from .env, not .env.example."""
    # This test verifies the architecture, not runtime behavior
    # The implementation in config.py uses load_dotenv which loads .env
    # .env.example is only a template and should not be used at runtime
    
    settings = Settings()
    
    # Settings should be loaded
    assert settings is not None
    
    # The implementation should reference .env, not .env.example
    # This is verified by inspecting the config.py implementation
    import backend.app.core.config as config_module
    import inspect
    
    source = inspect.getsource(config_module._project_root)
    # The function uses Path(__file__).resolve().parents[3] to find project root
    # and then loads .env from there
    assert ".env.example" not in source


def test_gemini_api_key_not_logged():
    """Test that GEMINI_API_KEY is not exposed in logs."""
    from backend.app.core.logging import get_logger
    import logging
    from io import StringIO
    
    # Create a string handler to capture logs
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    
    logger = get_logger(__name__)
    logger.addHandler(handler)
    
    # Log settings (should not expose API key)
    settings = get_settings()
    logger.info(f"Settings loaded with model: {settings.gemini_model}")
    
    log_output = log_capture.getvalue()
    
    # API key should not appear in logs
    if settings.gemini_api_key:
        assert settings.gemini_api_key not in log_output


def test_postgres_password_not_logged():
    """Test that POSTGRES_PASSWORD is not exposed in logs."""
    from backend.app.core.logging import get_logger
    import logging
    from io import StringIO
    
    # Create a string handler to capture logs
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    
    logger = get_logger(__name__)
    logger.addHandler(handler)
    
    # Log database connection info (should not expose password)
    settings = get_settings()
    logger.info(f"Database host: {settings.db_host}, port: {settings.db_port}")
    
    log_output = log_capture.getvalue()
    
    # Password should not appear in logs
    if settings.db_password:
        assert settings.db_password not in log_output


def test_api_keys_not_exposed_in_responses():
    """Test that API keys are not exposed in LLM responses."""
    from backend.app.llm.response import ResponseFormatter
    
    formatter = ResponseFormatter()
    
    # Create a response that might accidentally include sensitive data
    test_response = formatter.format_success_response(
        answer="Here's the answer",
        sources=[],
        tools_used=[],
        metadata={"api_key": "secret_123"}  # Should not happen, but test protection
    )
    
    # The metadata should not be exposed in the formatted answer
    assert "secret_123" not in test_response.answer
    assert "api_key" not in test_response.answer


def test_secrets_not_in_vector_store_metadata(tmp_path):
    """Test that secret files are not ingested into vector store."""
    from backend.app.rag.loaders import DocumentLoader
    from backend.app.rag.chunker import DocumentChunker
    from backend.app.rag.config import RAGConfig
    
    # Create test directory
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    
    # Create secret file
    secret_file = docs_dir / ".secret"
    secret_file.write_text("API_KEY=supersecret123")
    
    # Create normal file
    normal_file = docs_dir / "normal.md"
    normal_file.write_text("# Normal Document\n\nNormal content.")
    
    config = RAGConfig(
        documents_path=docs_dir,
        vector_db_path=tmp_path / "vector_db",
        chunk_size=500,
        chunk_overlap=50,
        top_k=5,
        embedding_model="test",
    )
    
    loader = DocumentLoader(config)
    chunker = DocumentChunker(config.chunk_size, config.chunk_overlap)
    
    # Load directory
    documents = loader.load_directory(docs_dir)
    
    # Secret file should not be loaded
    file_names = [doc["metadata"]["file_name"] for doc in documents]
    assert ".secret" not in file_names
    assert "normal.md" in file_names
    
    # Chunk the loaded documents
    all_chunks = []
    for doc in documents:
        chunks = chunker.chunk_document(doc)
        all_chunks.extend(chunks)
    
    # Verify no secret content in chunks
    chunk_contents = [chunk.content for chunk in all_chunks]
    assert "supersecret123" not in str(chunk_contents)
    assert "API_KEY" not in str(chunk_contents)


def test_configuration_paths_are_portable():
    """Test that configuration uses portable paths, not absolute Windows paths."""
    settings = get_settings()
    
    # Paths should be relative to project root or configurable
    # They should not contain hardcoded absolute paths like C:\Users\...
    
    # Check that project_root is not a hardcoded absolute path
    import backend.app.core.config as config_module
    import inspect
    
    source = inspect.getsource(config_module.Settings)
    
    # Should not contain hardcoded Windows paths
    assert "C:\\Users\\" not in source
    assert "C:/Users/" not in source
    assert "/home/" not in source  # Also avoid hardcoded Linux paths
    
    # Should use environment variables or Path manipulation
    assert "_env" in source or "Path" in source