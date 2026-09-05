"""Response formatter for LLM outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ChatResponse:
    """Structured chat response."""

    answer: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "answer": self.answer,
            "sources": self.sources,
            "tools_used": self.tools_used,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


class ResponseFormatter:
    """Format LLM responses into structured outputs."""

    def __init__(self):
        pass

    def format_success_response(
        self,
        answer: str,
        sources: Optional[List[Dict[str, Any]]] = None,
        tools_used: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ChatResponse:
        """Format a successful response."""
        return ChatResponse(
            answer=answer,
            sources=sources or [],
            tools_used=tools_used or [],
            metadata=metadata or {},
        )

    def format_domain_rejection_response(self) -> ChatResponse:
        """Format a response for out-of-domain questions."""
        return ChatResponse(
            answer="I'm specialized in payment and financial reconciliation. Please ask me about transactions, settlements, mismatches, reconciliation results, anomalies, or related analysis.",
            sources=[],
            tools_used=[],
            metadata={"domain_rejected": True},
        )

    def format_error_response(self, error_message: str) -> ChatResponse:
        """Format an error response."""
        return ChatResponse(
            answer=f"I encountered an error: {error_message}. Please try again or contact support.",
            sources=[],
            tools_used=[],
            metadata={"error": error_message},
        )

    def format_insufficient_evidence_response(self, missing_info: str) -> ChatResponse:
        """Format a response when evidence is insufficient."""
        return ChatResponse(
            answer=f"I couldn't verify that information from the available reconciliation data. {missing_info}",
            sources=[],
            tools_used=[],
            metadata={"insufficient_evidence": True, "missing_info": missing_info},
        )

    def extract_sources_from_context(
        self,
        rag_sources: Optional[List[Dict[str, Any]]] = None,
        database_sources: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Extract and format source information."""
        sources = []

        if rag_sources:
            for source in rag_sources:
                sources.append(
                    {
                        "type": "documentation",
                        "source": source.get("metadata", {}).get("source", "Unknown"),
                        "section": source.get("metadata", {}).get("section", "Unknown"),
                        "content_preview": source.get("content", "")[:100] + "...",
                    }
                )

        if database_sources:
            for source in database_sources:
                sources.append(
                    {
                        "type": "database",
                        "source": source.get("source_type", "Database"),
                        "id": source.get("id", "Unknown"),
                    }
                )

        return sources
