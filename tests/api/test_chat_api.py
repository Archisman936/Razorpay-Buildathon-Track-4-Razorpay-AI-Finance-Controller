"""Tests for chat API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from backend.app.main import create_app
from backend.app.llm.response import ChatResponse


@pytest.fixture
def client():
    """Create a test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_agent():
    """Mock the reconciliation agent."""
    agent = Mock()
    agent.chat = Mock(return_value=ChatResponse(
        answer="Test response",
        sources=[],
        tools_used=["RAG"],
        metadata={"test": "data"}
    ))
    agent.health_check = Mock(return_value={
        "ok": True,
        "components": {"gemini": {"ok": True}, "rag": {"ok": True}},
        "conversation_history_length": 0
    })
    agent.reset_conversation = Mock()
    return agent


def test_chat_message_endpoint(client, mock_agent):
    """Test the chat message endpoint."""
    with patch('backend.app.api.routes.chat.get_agent', return_value=mock_agent):
        response = client.post(
            "/api/v1/chat/message",
            json={"message": "What is settlement reconciliation?"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "tools_used" in data
        assert data["answer"] == "Test response"
        assert "RAG" in data["tools_used"]


def test_chat_message_with_reset(client, mock_agent):
    """Test chat message with conversation reset."""
    with patch('backend.app.api.routes.chat.get_agent', return_value=mock_agent):
        response = client.post(
            "/api/v1/chat/message",
            json={
                "message": "What is settlement reconciliation?",
                "reset_conversation": True
            }
        )
        
        assert response.status_code == 200
        mock_agent.reset_conversation.assert_called_once()


def test_chat_message_empty_message(client):
    """Test chat message with empty message."""
    response = client.post(
        "/api/v1/chat/message",
        json={"message": ""}
    )
    
    # Should fail validation
    assert response.status_code == 422


def test_chat_message_missing_message(client):
    """Test chat message without message field."""
    response = client.post(
        "/api/v1/chat/message",
        json={}
    )
    
    # Should fail validation
    assert response.status_code == 422


def test_reset_chat_endpoint(client, mock_agent):
    """Test the reset chat endpoint."""
    with patch('backend.app.api.routes.chat.get_agent', return_value=mock_agent):
        response = client.post("/api/v1/chat/reset")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "message" in data
        mock_agent.reset_conversation.assert_called_once()


def test_chat_health_endpoint(client, mock_agent):
    """Test the chat health endpoint."""
    with patch('backend.app.api.routes.chat.get_agent', return_value=mock_agent):
        response = client.get("/api/v1/chat/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "components" in data
        assert "conversation_history_length" in data
        assert data["ok"] is True


def test_chat_health_error_handling(client):
    """Test chat health endpoint error handling."""
    with patch('backend.app.api.routes.chat.get_agent', side_effect=Exception("Agent error")):
        response = client.get("/api/v1/chat/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert "error" in data


def test_chat_message_agent_error(client, mock_agent):
    """Test chat message when agent raises an error."""
    mock_agent.chat.side_effect = Exception("Agent processing error")
    
    with patch('backend.app.api.routes.chat.get_agent', return_value=mock_agent):
        response = client.post(
            "/api/v1/chat/message",
            json={"message": "Test question"}
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data


def test_chat_message_response_structure(client, mock_agent):
    """Test that chat message response has correct structure."""
    mock_agent.chat.return_value = ChatResponse(
        answer="Detailed answer",
        sources=[
            {"type": "documentation", "source": "test.md", "section": "Introduction"}
        ],
        tools_used=["RAG", "DATABASE"],
        confidence=0.95,
        metadata={"domain": "IN_SCOPE"}
    )
    
    with patch('backend.app.api.routes.chat.get_agent', return_value=mock_agent):
        response = client.post(
            "/api/v1/chat/message",
            json={"message": "Test question"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Detailed answer"
        assert len(data["sources"]) == 1
        assert data["sources"][0]["type"] == "documentation"
        assert "RAG" in data["tools_used"]
        assert "DATABASE" in data["tools_used"]
        assert data["confidence"] == 0.95
        assert data["metadata"]["domain"] == "IN_SCOPE"


def test_reset_chat_error_handling(client):
    """Test reset chat endpoint error handling."""
    with patch('backend.app.api.routes.chat.get_agent', side_effect=Exception("Reset error")):
        response = client.post("/api/v1/chat/reset")
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data