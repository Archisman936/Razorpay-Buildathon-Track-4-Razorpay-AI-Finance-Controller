"""Tests for LLM prompts."""

from __future__ import annotations

import pytest
from backend.app.llm.prompts import (
    get_system_prompt,
    get_domain_classification_prompt,
    get_intent_analysis_prompt,
)


def test_system_prompt_exists():
    """Test that system prompt is available."""
    prompt = get_system_prompt()
    assert prompt is not None
    assert len(prompt) > 0
    assert "Razorpay" in prompt
    assert "reconciliation" in prompt.lower()


def test_system_prompt_contains_key_instructions():
    """Test that system prompt contains key instructions."""
    prompt = get_system_prompt()

    # Check for key sections
    assert "Your Role" in prompt
    assert "Strict Rules" in prompt
    assert "Domain Scope" in prompt
    assert "Out-of-Scope Handling" in prompt

    # Check for important rules
    assert "Never invent financial facts" in prompt
    assert "Never invent ML results" in prompt
    assert "Never override reconciliation results" in prompt


def test_domain_classification_prompt():
    """Test domain classification prompt generation."""
    question = "What is settlement reconciliation?"
    prompt = get_domain_classification_prompt(question)

    assert question in prompt
    assert "IN_SCOPE" in prompt
    assert "OUT_OF_SCOPE" in prompt


def test_intent_analysis_prompt():
    """Test intent analysis prompt generation."""
    question = "Why is TXN123 unmatched?"
    prompt = get_intent_analysis_prompt(question)

    assert question in prompt
    assert "requires_rag" in prompt
    assert "requires_database" in prompt
    assert "requires_ml" in prompt
    assert "requires_reconciliation" in prompt


def test_prompts_are_not_empty():
    """Test that no prompts are empty."""
    assert len(get_system_prompt()) > 0
    assert len(get_domain_classification_prompt("test")) > 0
    assert len(get_intent_analysis_prompt("test")) > 0
