"""Tests for GeminiService and Gemini 3.8 Flash thinking_level configuration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from google.genai import types

from backend.app.core.config import Settings
from backend.app.llm.gemini_service import GeminiService, GeminiServiceError, get_gemini_service


@pytest.fixture
def gemini_settings_38():
    settings = Settings()
    settings.gemini_api_key = "test-api-key"
    settings.gemini_model = "gemini-3.8-flash"
    return settings


@pytest.fixture
def gemini_settings_non_38():
    settings = Settings()
    settings.gemini_api_key = "test-api-key"
    settings.gemini_model = "gemini-3.6-flash"
    return settings


def test_gemini_38_generate_content_configures_thinking_level_low(gemini_settings_38):
    """Verify Gemini 3.8 Flash uses thinking_level='low' in ThinkingConfig."""
    service = GeminiService(settings=gemini_settings_38)
    
    # Mock client.models.generate_content
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Sample response"
    mock_client.models.generate_content.return_value = mock_response
    service._client = mock_client
    
    result = service.generate_content("Hello test prompt")
    
    assert result == "Sample response"
    mock_client.models.generate_content.assert_called_once()
    
    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-3.8-flash"
    assert call_kwargs["contents"] == "Hello test prompt"
    
    config = call_kwargs["config"]
    assert isinstance(config, types.GenerateContentConfig)
    assert config.thinking_config is not None
    assert config.thinking_config.thinking_level == types.ThinkingLevel.LOW


def test_gemini_non_38_does_not_force_thinking_level(gemini_settings_non_38):
    """Verify non-3.8 models do not pass thinking_config."""
    service = GeminiService(settings=gemini_settings_non_38)
    
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Sample response"
    mock_client.models.generate_content.return_value = mock_response
    service._client = mock_client
    
    result = service.generate_content("Hello test prompt")
    assert result == "Sample response"
    
    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    config = call_kwargs["config"]
    assert config.thinking_config is None


def test_gemini_38_chat_configures_thinking_level_low(gemini_settings_38):
    """Verify Gemini 3.8 Flash chat session configures thinking_level='low'."""
    service = GeminiService(settings=gemini_settings_38)
    
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Chat reply"
    mock_chat.send_message.return_value = mock_response
    mock_client.chats.create.return_value = mock_chat
    service._client = mock_client
    
    reply = service.chat("How does reconciliation work?")
    assert reply == "Chat reply"
    
    mock_client.chats.create.assert_called_once()
    create_kwargs = mock_client.chats.create.call_args.kwargs
    assert create_kwargs["model"] == "gemini-3.8-flash"
    
    config = create_kwargs["config"]
    assert isinstance(config, types.GenerateContentConfig)
    assert config.thinking_config is not None
    assert config.thinking_config.thinking_level == types.ThinkingLevel.LOW


def test_gemini_service_validation():
    """Verify validation when api key or model is missing."""
    empty_settings = Settings()
    empty_settings.gemini_api_key = ""
    empty_settings.gemini_model = ""
    with pytest.raises(GeminiServiceError, match="GEMINI_API_KEY is not configured"):
        GeminiService(settings=empty_settings)
