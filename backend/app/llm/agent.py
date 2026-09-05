"""LLM Agent - orchestrator for chatbot intelligence."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from backend.app.core.logging import get_logger
from backend.app.llm.context import ContextBuilder, QueryContext
from backend.app.llm.gemini_service import GeminiService, GeminiServiceError, get_gemini_service
from backend.app.llm.prompts import (
    get_domain_classification_prompt,
    get_intent_analysis_prompt,
    get_system_prompt,
)
from backend.app.llm.response import ChatResponse, ResponseFormatter
from backend.app.llm.tools import DatabaseTool, MLTool, ReconciliationTool
from backend.app.rag import RAGService, RAGServiceError, get_rag_service

logger = get_logger(__name__)


class AgentError(Exception):
    """Raised when agent operations fail."""


class ReconciliationAgent:
    """Main agent that orchestrates LLM, RAG, and tools."""

    def __init__(
        self,
        gemini_service: Optional[GeminiService] = None,
        rag_service: Optional[RAGService] = None,
        reconciliation_tool: Optional[ReconciliationTool] = None,
        database_tool: Optional[DatabaseTool] = None,
        ml_tool: Optional[MLTool] = None,
    ):
        self.gemini_service = gemini_service or get_gemini_service()
        self.rag_service = rag_service or get_rag_service()
        self.reconciliation_tool = reconciliation_tool or ReconciliationTool()
        self.database_tool = database_tool or DatabaseTool()
        self.ml_tool = ml_tool or MLTool()
        self.context_builder = ContextBuilder()
        self.response_formatter = ResponseFormatter()
        self.conversation_history: List[Dict[str, str]] = []

    def classify_and_analyze(self, question: str) -> tuple[str, dict]:
        """Classify domain AND analyze intent in a single LLM call to save quota."""
        try:
            prompt = (
                f"You are a financial reconciliation AI assistant classifier.\n"
                f"User question: \"{question}\"\n\n"
                f"Respond with ONLY valid JSON (no markdown, no backticks):\n"
                f"{{\n"
                f"  \"domain\": \"IN_SCOPE\" or \"OUT_OF_SCOPE\",\n"
                f"  \"requires_rag\": true/false,\n"
                f"  \"requires_database\": true/false,\n"
                f"  \"requires_ml\": true/false,\n"
                f"  \"requires_reconciliation\": true/false\n"
                f"}}\n\n"
                f"Rules:\n"
                f"- IN_SCOPE = finance, reconciliation, payments, transactions, settlements, ML models, exceptions, bank records\n"
                f"- OUT_OF_SCOPE = politics, weather, cooking, entertainment, anything unrelated to fintech/finance\n"
                f"- requires_rag = needs financial rules/documentation lookup\n"
                f"- requires_database = needs specific record data\n"
                f"- requires_reconciliation = asks about a specific transaction match/mismatch"
            )
            response = self.gemini_service.generate_content(prompt, temperature=0.1, max_output_tokens=120)
            cleaned = re.sub(r"```(?:json)?", "", response).strip()
            json_match = re.search(r"\{[\s\S]*\}", cleaned)
            parsed = json.loads(json_match.group()) if json_match else json.loads(cleaned)

            domain = "IN_SCOPE" if str(parsed.get("domain", "IN_SCOPE")).upper() == "IN_SCOPE" else "OUT_OF_SCOPE"
            intent = {
                "requires_rag":             bool(parsed.get("requires_rag", True)),
                "requires_database":        bool(parsed.get("requires_database", False)),
                "requires_ml":              bool(parsed.get("requires_ml", False)),
                "requires_reconciliation":  bool(parsed.get("requires_reconciliation", False)),
                "reasoning": "combined classification",
            }
            return domain, intent

        except Exception as e:
            logger.warning("Combined classify_and_analyze failed (%s), using safe defaults", e)
            return "IN_SCOPE", {
                "requires_rag": True, "requires_database": False,
                "requires_ml": False, "requires_reconciliation": False,
                "reasoning": "defaults after error",
            }

    def classify_domain(self, question: str) -> str:
        """Classify if question is in-scope or out-of-scope."""
        domain, _ = self.classify_and_analyze(question)
        return domain

    def analyze_intent(self, question: str) -> dict:
        """Analyze intent to determine required information sources."""
        _, intent = self.classify_and_analyze(question)
        return intent


    def extract_transaction_id(self, question: str) -> Optional[tuple[str, str]]:
        """Extract transaction ID and type from question."""
        # Look for patterns like TXN123, PAY_001, BNK_001, STL_001
        patterns = [
            (r"(BNK_\w+)", "bank_record"),
            (r"(PAY_\w+)", "payment"),
            (r"(STL_\w+)", "settlement"),
            (r"(ORD_\w+)", "order"),
            (r"(TXN\w+)", "transaction"),  # Generic
        ]

        for pattern, t_type in patterns:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                return match.group(1), t_type

        return None

    def process_question(self, question: str) -> ChatResponse:
        """Process a user question through the complete pipeline."""
        logger.info("Processing question: %s", question[:100])

        # Step 1+2: Combined domain classification + intent analysis (single LLM call)
        domain, intent = self.classify_and_analyze(question)
        if domain == "OUT_OF_SCOPE":
            logger.info("Question classified as out-of-scope")
            return self.response_formatter.format_domain_rejection_response()

        logger.info("Intent analysis: %s", intent)

        # Step 3: Extract transaction information if present
        transaction_info = self.extract_transaction_id(question)

        # Step 4: Gather evidence based on intent
        rag_results = []
        database_results = []
        reconciliation_results = None
        ml_results = None
        tools_used = []

        # RAG retrieval
        if intent.get("requires_rag", True):  # Default to RAG
            try:
                rag_results = self.rag_service.retrieve(question)
                if rag_results:
                    tools_used.append("RAG")
                    logger.info("Retrieved %d RAG chunks", len(rag_results))
            except RAGServiceError as e:
                logger.warning("RAG retrieval failed: %s", e)

        # Database/reconciliation for specific transactions
        if transaction_info and (intent.get("requires_reconciliation", False) or intent.get("requires_database", False)):
            trans_id, trans_type = transaction_info
            # Fetch direct database record
            try:
                db_record = self.database_tool.get_transaction(trans_id, trans_type)
                if db_record:
                    database_results.append(db_record)
                    if "DATABASE" not in tools_used:
                        tools_used.append("DATABASE")
                    logger.info("Retrieved database record for %s", trans_id)
            except Exception as e:
                logger.error("Database record retrieval failed: %s", e)

            # Fetch reconciliation result
            try:
                reconciliation_results = self.reconciliation_tool.get_reconciliation_result(
                    source_type=trans_type,
                    source_id=trans_id,
                    include_ml=intent.get("requires_ml", True),
                    include_exception=True,
                )
                if reconciliation_results and "error" not in reconciliation_results:
                    tools_used.append("RECONCILIATION")
                    logger.info("Retrieved reconciliation result for %s", trans_id)

                    # Extract ML results if available
                    if intent.get("requires_ml", True):
                        ml_results = self.ml_tool.get_ml_analysis_from_reconciliation(
                            reconciliation_results
                        )
                        if ml_results:
                            tools_used.append("ML")

            except Exception as e:
                logger.error("Reconciliation retrieval failed: %s", e)

        # Database queries for general information
        if intent.get("requires_database", False) and not database_results:
            try:
                # Get summary stats if asking about counts/overview
                if any(
                    word in question.lower()
                    for word in ["how many", "count", "summary", "overview", "unmatched"]
                ):
                    summary = self.reconciliation_tool.get_reconciliation_summary()
                    database_results.append(summary)
                    tools_used.append("DATABASE")
                    logger.info("Retrieved database summary")

            except Exception as e:
                logger.error("Database query failed: %s", e)

        # Step 5: Build context
        context = self.context_builder.build_context(
            user_question=question,
            domain_classification=domain,
            intent_analysis=intent,
            rag_results=rag_results,
            database_results=database_results,
            reconciliation_results=reconciliation_results,
            ml_results=ml_results,
            conversation_history=self.conversation_history,
        )

        # Step 6: Generate response
        try:
            system_prompt = get_system_prompt()
            context_prompt = context.to_llm_prompt()

            full_prompt = f"{system_prompt}\n\n{context_prompt}"

            answer = self.gemini_service.generate_content(
                full_prompt,
                temperature=0.7,
            )

            # Update conversation history
            self.conversation_history.append({"role": "user", "parts": question})
            self.conversation_history.append({"role": "model", "parts": answer})

            # Keep conversation history manageable
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]

            # Extract sources
            sources = self.response_formatter.extract_sources_from_context(
                rag_sources=rag_results,
                database_sources=database_results,
            )

            logger.info("Generated response for question: %s", question[:50])
            return self.response_formatter.format_success_response(
                answer=answer,
                sources=sources,
                tools_used=tools_used,
                metadata={
                    "domain": domain,
                    "intent": intent,
                    "transaction_id": transaction_info[0] if transaction_info else None,
                },
            )

        except GeminiServiceError as e:
            logger.error("Response generation failed: %s", e)
            return self.response_formatter.format_error_response(str(e))

    def chat(self, message: str) -> ChatResponse:
        """Public chat interface."""
        return self.process_question(message)

    def reset_conversation(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []
        logger.info("Conversation history cleared")

    def health_check(self) -> Dict[str, Any]:
        """Check health of all agent components."""
        gemini_check = self.gemini_service.health_check()
        rag_check = self.rag_service.health_check()
        checks = {
            "gemini": gemini_check,
            "rag": rag_check,
        }

        gemini_ok = gemini_check.get("ok", False)
        rag_ok = (
            rag_check.get("ok", False)
            or rag_check.get("rag_service") == "ok"
            or rag_check.get("vector_store", {}).get("ok", False)
        )
        all_ok = gemini_ok and rag_ok

        return {
            "ok": all_ok,
            "components": checks,
            "conversation_history_length": len(self.conversation_history),
        }


def get_agent() -> ReconciliationAgent:
    """Factory function to get agent instance."""
    return ReconciliationAgent()
