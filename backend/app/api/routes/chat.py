"""Chat API endpoints for LLM agent."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.llm import ReconciliationAgent, get_agent
from backend.app.llm.response import ChatResponse

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str = Field(..., description="User message/question", min_length=1)
    reset_conversation: bool = Field(default=False, description="Reset conversation history")


class ChatResponseModel(BaseModel):
    """Response model for chat endpoint."""

    answer: str
    sources: list[dict] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    confidence: float | None = None
    metadata: dict = Field(default_factory=dict)


@router.post("/message", response_model=ChatResponseModel)
def chat_message(request: ChatRequest) -> dict:
    """Process a chat message and return the agent's response."""
    try:
        agent = get_agent()

        if request.reset_conversation:
            agent.reset_conversation()

        response = agent.chat(request.message)
        return response.to_dict()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/reset")
def reset_chat() -> dict:
    """Reset the conversation history."""
    try:
        agent = get_agent()
        agent.reset_conversation()
        return {"status": "success", "message": "Conversation history cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/health")
def chat_health() -> dict:
    """Check the health of the chat/agent system."""
    try:
        agent = get_agent()
        return agent.health_check()
    except Exception as e:
        return {"ok": False, "error": str(e)}
