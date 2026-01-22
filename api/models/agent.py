"""Pydantic models for Agent API requests and responses."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """Request model for agent chat endpoint."""

    message: str = Field(..., description="User input message", min_length=1)
    workspace_id: Optional[str] = Field(
        None, description="Workspace ID to use (creates new if not provided)"
    )
    thread_id: Optional[str] = Field(
        None, description="Thread ID for conversation continuity (creates new if not provided)"
    )
    plan_mode: bool = Field(
        default=False, description="Enable plan mode (agent submits plan for approval)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Hello, can you help me analyze this code?",
                "workspace_id": None,
                "thread_id": None,
                "plan_mode": False,
            }
        }


class AgentChatResponse(BaseModel):
    """Response model for agent chat endpoint."""

    success: bool = Field(..., description="Whether the request was successful")
    message: str = Field(..., description="Agent's response message")
    thread_id: str = Field(..., description="Thread ID for this conversation")
    workspace_id: Optional[str] = Field(None, description="Workspace ID used")
    tool_calls: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of tools used during execution"
    )
    error: Optional[str] = Field(None, description="Error message if request failed")

