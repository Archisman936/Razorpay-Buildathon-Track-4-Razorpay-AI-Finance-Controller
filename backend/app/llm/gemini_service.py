"""Gemini LLM service."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from google import genai
from google.genai import types
from google.genai.errors import APIError

from backend.app.core.config import Settings, get_settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class GeminiServiceError(Exception):
    """Raised when Gemini service operations fail."""


class GeminiService:
    """Service for interacting with Google Gemini API using google.genai SDK."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._client: Optional[genai.Client] = None
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate that required configuration is present."""
        if not self.settings.gemini_api_key:
            raise GeminiServiceError("GEMINI_API_KEY is not configured")
        if not self.settings.gemini_model:
            raise GeminiServiceError("GEMINI_MODEL is not configured")

    @property
    def client(self) -> genai.Client:
        """Lazy load Gemini client."""
        if self._client is None:
            try:
                self._client = genai.Client(api_key=self.settings.gemini_api_key)
                logger.info("Gemini client initialized with model: %s", self.settings.gemini_model)
            except Exception as e:
                raise GeminiServiceError(f"Failed to initialize Gemini client: {e}") from e
        return self._client

    def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
    ) -> str:
        """Generate content using Gemini."""
        if not prompt or not prompt.strip():
            raise GeminiServiceError("Prompt cannot be empty")

        config_kwargs: Dict[str, Any] = {
            "temperature": temperature,
        }
        if max_output_tokens:
            # Modern Gemini models need sufficient token ceiling for output generation
            config_kwargs["max_output_tokens"] = max(max_output_tokens, 500)

        # Gemini 3.8 Flash migration guidance: use thinking_level="low" instead of deprecated thinking_budget
        if "3.8" in self.settings.gemini_model and "flash" in self.settings.gemini_model.lower():
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_level="low"
            )

        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        config = types.GenerateContentConfig(**config_kwargs)

        # Retry with exponential backoff on transient errors (e.g. 503, 429)
        max_retries = 4
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=prompt,
                    config=config,
                )

                if response.text:
                    logger.info("Generated %d characters from Gemini", len(response.text))
                    return response.text
                elif response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if getattr(part, "text", None):
                            return part.text
                    raise GeminiServiceError("Empty response text from Gemini")
                else:
                    raise GeminiServiceError("Empty response from Gemini")

            except APIError as e:
                last_error = e
                logger.warning("Gemini API error (attempt %d/%d): %s", attempt, max_retries, e)
                if attempt < max_retries:
                    sleep_time = attempt * 2.0
                    err_msg = str(e)
                    if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                        import re
                        match = re.search(r"retry in (\d+(?:\.\d+)?)s", err_msg, re.IGNORECASE)
                        if match:
                            sleep_time = float(match.group(1)) + 1.0
                        else:
                            sleep_time = max(sleep_time, 15.0)
                        logger.info("Rate limit hit, backing off for %.1f seconds...", sleep_time)
                    time.sleep(sleep_time)
                else:
                    raise GeminiServiceError(f"Failed to generate content: {e}") from e
            except GeminiServiceError:
                raise
            except Exception as e:
                logger.error("Gemini generation failed: %s", e)
                raise GeminiServiceError(f"Failed to generate content: {e}") from e

        raise GeminiServiceError(f"Failed to generate content after retries: {last_error}")

    def chat(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
    ) -> str:
        """Generate a chat response with conversation history."""
        if not message or not message.strip():
            raise GeminiServiceError("Message cannot be empty")

        try:
            config_kwargs: Dict[str, Any] = {}
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction
            if "3.8" in self.settings.gemini_model and "flash" in self.settings.gemini_model.lower():
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    thinking_level="low"
                )
            config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

            # Convert history if provided
            formatted_history: List[types.Content] = []
            if conversation_history:
                for turn in conversation_history:
                    role = turn.get("role", "user")
                    # Handle both "parts" and "content"
                    raw_parts = turn.get("parts") or turn.get("content", "")
                    if isinstance(raw_parts, str):
                        parts = [types.Part.from_text(text=raw_parts)]
                    elif isinstance(raw_parts, list):
                        parts = [types.Part.from_text(text=str(p)) for p in raw_parts]
                    else:
                        parts = [types.Part.from_text(text=str(raw_parts))]
                    formatted_history.append(types.Content(role=role, parts=parts))

            chat_session = self.client.chats.create(
                model=self.settings.gemini_model,
                history=formatted_history if formatted_history else None,
                config=config,
            )

            # Retry on transient API errors
            max_retries = 4
            for attempt in range(1, max_retries + 1):
                try:
                    response = chat_session.send_message(message)
                    if response.text:
                        logger.info("Chat response generated: %d chars", len(response.text))
                        return response.text
                    elif response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                        for part in response.candidates[0].content.parts:
                            if getattr(part, "text", None):
                                return part.text
                        raise GeminiServiceError("Empty chat response from Gemini")
                    else:
                        raise GeminiServiceError("Empty chat response from Gemini")
                except APIError as e:
                    if attempt < max_retries:
                        sleep_time = attempt * 2.0
                        err_msg = str(e)
                        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                            import re
                            match = re.search(r"retry in (\d+(?:\.\d+)?)s", err_msg, re.IGNORECASE)
                            if match:
                                sleep_time = float(match.group(1)) + 1.0
                            else:
                                sleep_time = max(sleep_time, 15.0)
                            logger.info("Chat rate limit hit, backing off for %.1f seconds...", sleep_time)
                        time.sleep(sleep_time)
                    else:
                        raise GeminiServiceError(f"Failed to generate chat response: {e}") from e

        except GeminiServiceError:
            raise
        except Exception as e:
            logger.error("Gemini chat failed: %s", e)
            raise GeminiServiceError(f"Failed to generate chat response: {e}") from e

    def health_check(self) -> Dict[str, Any]:
        """Check if Gemini service is operational."""
        try:
            # Simple test call
            test_response = self.generate_content("Ping", max_output_tokens=10)
            return {
                "ok": True,
                "model": self.settings.gemini_model,
                "message": "Gemini service is operational",
            }
        except Exception as e:
            return {
                "ok": False,
                "model": self.settings.gemini_model,
                "error": str(e),
            }


def get_gemini_service(settings: Optional[Settings] = None) -> GeminiService:
    """Factory function to get Gemini service instance."""
    return GeminiService(settings=settings)

