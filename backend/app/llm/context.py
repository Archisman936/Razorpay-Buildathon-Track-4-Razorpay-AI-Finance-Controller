"""Context builder for combining evidence from multiple sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Evidence:
    """Evidence from a specific source."""

    source: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: Optional[float] = None


@dataclass
class QueryContext:
    """Structured context for LLM query."""

    user_question: str
    domain_classification: str
    intent_analysis: Dict[str, Any]
    rag_evidence: List[Evidence] = field(default_factory=list)
    database_evidence: List[Evidence] = field(default_factory=list)
    reconciliation_evidence: List[Evidence] = field(default_factory=list)
    ml_evidence: List[Evidence] = field(default_factory=list)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)

    def has_rag_evidence(self) -> bool:
        """Check if RAG evidence is available."""
        return len(self.rag_evidence) > 0

    def has_database_evidence(self) -> bool:
        """Check if database evidence is available."""
        return len(self.database_evidence) > 0

    def has_reconciliation_evidence(self) -> bool:
        """Check if reconciliation evidence is available."""
        return len(self.reconciliation_evidence) > 0

    def has_ml_evidence(self) -> bool:
        """Check if ML evidence is available."""
        return len(self.ml_evidence) > 0

    def to_llm_prompt(self) -> str:
        """Convert context to structured LLM prompt."""
        sections = []

        sections.append(f"USER QUESTION:\n{self.user_question}\n")

        if self.has_reconciliation_evidence():
            sections.append("RECONCILIATION EVIDENCE:")
            for evidence in self.reconciliation_evidence:
                sections.append(f"Source: {evidence.source}")
                sections.append(f"Content: {evidence.content}")
                if evidence.metadata:
                    sections.append(f"Metadata: {evidence.metadata}")
                sections.append("")

        if self.has_database_evidence():
            sections.append("DATABASE EVIDENCE:")
            for evidence in self.database_evidence:
                sections.append(f"Source: {evidence.source}")
                sections.append(f"Content: {evidence.content}")
                if evidence.metadata:
                    sections.append(f"Metadata: {evidence.metadata}")
                sections.append("")

        if self.has_ml_evidence():
            sections.append("ML EVIDENCE:")
            for evidence in self.ml_evidence:
                sections.append(f"Source: {evidence.source}")
                sections.append(f"Content: {evidence.content}")
                if evidence.metadata:
                    sections.append(f"Metadata: {evidence.metadata}")
                sections.append("")

        if self.has_rag_evidence():
            sections.append("RAG EVIDENCE:")
            for evidence in self.rag_evidence:
                sections.append(f"Source: {evidence.source}")
                sections.append(f"Content: {evidence.content}")
                if evidence.metadata:
                    sections.append(f"Metadata: {evidence.metadata}")
                sections.append("")

        return "\n".join(sections)


class ContextBuilder:
    """Build structured context from multiple evidence sources."""

    def __init__(self):
        pass

    def build_context(
        self,
        user_question: str,
        domain_classification: str,
        intent_analysis: Dict[str, Any],
        rag_results: Optional[List[Dict[str, Any]]] = None,
        database_results: Optional[List[Dict[str, Any]]] = None,
        reconciliation_results: Optional[Dict[str, Any]] = None,
        ml_results: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> QueryContext:
        """Build a complete query context from all available sources."""
        context = QueryContext(
            user_question=user_question,
            domain_classification=domain_classification,
            intent_analysis=intent_analysis,
            conversation_history=conversation_history or [],
        )

        # Add RAG evidence
        if rag_results:
            for result in rag_results:
                context.rag_evidence.append(
                    Evidence(
                        source=result.get("metadata", {}).get("source", "RAG"),
                        content=result.get("content", ""),
                        metadata=result.get("metadata", {}),
                    )
                )

        # Add database evidence
        if database_results:
            for result in database_results:
                context.database_evidence.append(
                    Evidence(
                        source="DATABASE",
                        content=str(result),
                        metadata={"source_type": result.get("source_type", "unknown")},
                    )
                )

        # Add reconciliation evidence
        if reconciliation_results:
            context.reconciliation_evidence.append(
                Evidence(
                    source="RECONCILIATION_ENGINE",
                    content=self._format_reconciliation_result(reconciliation_results),
                    metadata=reconciliation_results,
                )
            )

        # Add ML evidence
        if ml_results:
            context.ml_evidence.append(
                Evidence(
                    source="ML_MODEL",
                    content=self._format_ml_result(ml_results),
                    metadata=ml_results,
                )
            )

        logger.info(
            "Built context with %d RAG, %d DB, %d RECON, %d ML evidence items",
            len(context.rag_evidence),
            len(context.database_evidence),
            len(context.reconciliation_evidence),
            len(context.ml_evidence),
        )

        return context

    def _format_reconciliation_result(self, result: Dict[str, Any]) -> str:
        """Format reconciliation result for display."""
        parts = []
        if "status" in result:
            parts.append(f"Status: {result['status']}")
        if "matched_record_id" in result:
            parts.append(f"Matched ID: {result['matched_record_id']}")
        if "amount_difference" in result:
            parts.append(f"Amount Difference: {result['amount_difference']}")
        if "reason_codes" in result:
            parts.append(f"Reason Codes: {result['reason_codes']}")
        if "explanation_facts" in result:
            parts.append(f"Explanation: {result['explanation_facts']}")
        return "\n".join(parts)

    def _format_ml_result(self, result: Dict[str, Any]) -> str:
        """Format ML result for display."""
        parts = []
        if "anomaly_score" in result:
            parts.append(f"Anomaly Score: {result['anomaly_score']}")
        if "exception_type" in result:
            parts.append(f"Exception Type: {result['exception_type']}")
        if "confidence" in result:
            parts.append(f"Confidence: {result['confidence']}")
        return "\n".join(parts)
