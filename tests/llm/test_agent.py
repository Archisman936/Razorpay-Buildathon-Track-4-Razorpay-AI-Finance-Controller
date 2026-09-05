"""Tests for LLM agent."""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch
from backend.app.llm.agent import ReconciliationAgent
from backend.app.llm.response import ChatResponse


@pytest.fixture
def mock_gemini_service():
    """Mock Gemini service."""
    service = Mock()
    service.generate_content = Mock(return_value="Test response")
    service.health_check = Mock(return_value={"ok": True})
    return service


@pytest.fixture
def mock_rag_service():
    """Mock RAG service."""
    service = Mock()
    service.retrieve = Mock(return_value=[])
    service.health_check = Mock(return_value={"ok": True, "document_count": 0})
    return service


@pytest.fixture
def mock_reconciliation_tool():
    """Mock reconciliation tool."""
    tool = Mock()
    tool.get_reconciliation_result = Mock(return_value={"status": "MATCHED"})
    tool.get_reconciliation_summary = Mock(return_value={"unmatched_bank_records": 5})
    return tool


@pytest.fixture
def agent(mock_gemini_service, mock_rag_service, mock_reconciliation_tool):
    """Create agent with mocked dependencies."""
    return ReconciliationAgent(
        gemini_service=mock_gemini_service,
        rag_service=mock_rag_service,
        reconciliation_tool=mock_reconciliation_tool,
    )


def test_agent_initialization(agent):
    """Test agent initialization."""
    assert agent is not None
    assert agent.gemini_service is not None
    assert agent.rag_service is not None
    assert agent.reconciliation_tool is not None


def test_agent_domain_classification_in_scope(agent, mock_gemini_service):
    """Test domain classification for in-scope question."""
    mock_gemini_service.generate_content.return_value = "IN_SCOPE"

    result = agent.classify_domain("What is settlement reconciliation?")

    assert result == "IN_SCOPE"
    mock_gemini_service.generate_content.assert_called_once()


def test_agent_domain_classification_out_of_scope(agent, mock_gemini_service):
    """Test domain classification for out-of-scope question."""
    mock_gemini_service.generate_content.return_value = "OUT_OF_SCOPE"

    result = agent.classify_domain("Who won the football match?")

    assert result == "OUT_OF_SCOPE"


def test_agent_domain_classification_error_handling(agent, mock_gemini_service):
    """Test domain classification error handling."""
    from backend.app.llm.gemini_service import GeminiServiceError
    mock_gemini_service.generate_content.side_effect = GeminiServiceError("API error")

    # Should default to IN_SCOPE on error
    result = agent.classify_domain("Test question")

    assert result == "IN_SCOPE"


def test_agent_intent_analysis(agent, mock_gemini_service):
    """Test intent analysis."""
    mock_gemini_service.generate_content.return_value = """
    {
        "requires_rag": true,
        "requires_database": false,
        "requires_ml": false,
        "requires_reconciliation": false,
        "reasoning": "Question about documentation"
    }
    """

    result = agent.analyze_intent("What is settlement reconciliation?")

    assert result["requires_rag"] is True
    assert result["requires_database"] is False
    assert result["requires_ml"] is False
    assert result["requires_reconciliation"] is False


def test_agent_transaction_id_extraction(agent):
    """Test transaction ID extraction."""
    test_cases = [
        ("Why is BNK_001 unmatched?", ("BNK_001", "bank_record")),
        ("Show me PAY_123 details", ("PAY_123", "payment")),
        ("What about STL_456?", ("STL_456", "settlement")),
        ("Check ORD_789", ("ORD_789", "order")),
        ("No ID here", None),
    ]

    for question, expected in test_cases:
        result = agent.extract_transaction_id(question)
        assert result == expected, f"Failed for: {question}"


def test_agent_out_of_scope_rejection(agent, mock_gemini_service):
    """Test that out-of-scope questions are rejected."""
    mock_gemini_service.generate_content.return_value = "OUT_OF_SCOPE"

    response = agent.process_question("Tell me a joke")

    assert isinstance(response, ChatResponse)
    assert "specialized in payment" in response.answer.lower()
    assert response.metadata.get("domain_rejected") is True


def test_agent_conversation_history(agent, mock_gemini_service, mock_rag_service):
    """Test conversation history management."""
    mock_gemini_service.generate_content.return_value = "IN_SCOPE"
    mock_rag_service.retrieve.return_value = []

    # First message
    agent.process_question("What is reconciliation?")
    assert len(agent.conversation_history) == 2  # user + model

    # Second message
    agent.process_question("How does it work?")
    assert len(agent.conversation_history) == 4  # 2 users + 2 models

    # Reset
    agent.reset_conversation()
    assert len(agent.conversation_history) == 0


def test_agent_health_check(agent, mock_gemini_service, mock_rag_service):
    """Test agent health check."""
    mock_gemini_service.health_check.return_value = {"ok": True}
    mock_rag_service.health_check.return_value = {"ok": True}

    health = agent.health_check()

    assert health["ok"] is True
    assert "gemini" in health["components"]
    assert "rag" in health["components"]
    assert "conversation_history_length" in health


def test_agent_tools_used_tracking(agent, mock_gemini_service, mock_rag_service):
    """Test that tools used are tracked."""
    mock_gemini_service.generate_content.return_value = "IN_SCOPE"
    mock_rag_service.retrieve.return_value = [
        {"content": "Test content", "metadata": {"source": "test.md"}}
    ]

    response = agent.process_question("What is settlement reconciliation?")

    assert "RAG" in response.tools_used


def test_response_formatter_domain_rejection():
    """Test response formatter for domain rejection."""
    from backend.app.llm.response import ResponseFormatter

    formatter = ResponseFormatter()
    response = formatter.format_domain_rejection_response()

    assert "specialized in payment" in response.answer.lower()
    assert response.metadata.get("domain_rejected") is True


def test_response_formatter_error():
    """Test response formatter for errors."""
    from backend.app.llm.response import ResponseFormatter

    formatter = ResponseFormatter()
    response = formatter.format_error_response("Test error")

    assert "error" in response.answer.lower()
    assert response.metadata.get("error") == "Test error"


def test_response_formatter_insufficient_evidence():
    """Test response formatter for insufficient evidence."""
    from backend.app.llm.response import ResponseFormatter

    formatter = ResponseFormatter()
    response = formatter.format_insufficient_evidence_response("Missing transaction data")

    assert "couldn't verify" in response.answer.lower()
    assert response.metadata.get("insufficient_evidence") is True
