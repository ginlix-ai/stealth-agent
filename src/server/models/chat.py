"""
Request and response models for Chat API endpoint.

This module defines Pydantic models for the /api/v1/chat/stream endpoint
that uses the ptc-agent library for code execution in Daytona sandboxes.
"""

from typing import Any, Dict, List, Literal, Mapping, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field

from src.server.models.additional_context import LastThreadContext


# =============================================================================
# HITL (Human-in-the-Loop) Models
# =============================================================================

class HITLDecision(BaseModel):
    """Decision for a single HITL action request."""

    type: Literal["approve", "reject"] = Field(
        description="Whether to approve or reject the action"
    )
    message: Optional[str] = Field(
        None,
        description="Feedback message, typically used when rejecting to explain why or request changes"
    )


class HITLResponse(BaseModel):
    """Response to a HITL interrupt containing decisions for each action request."""

    decisions: List[HITLDecision] = Field(
        description="List of decisions corresponding to each action request in the interrupt"
    )


def serialize_hitl_response_map(hitl_response: Mapping[str, Any]) -> Dict[str, dict]:
    """Convert validated HITLResponse models into plain dicts for LangGraph resume.

    LangChain's HumanInTheLoopMiddleware expects `resume` payloads to be
    subscriptable dicts (e.g. `{"decisions": [...]}`), not Pydantic model
    instances.
    """

    serialized: Dict[str, dict] = {}
    for interrupt_id, response in hitl_response.items():
        if hasattr(response, "model_dump"):
            serialized[interrupt_id] = response.model_dump()  # type: ignore[call-arg]
        elif hasattr(response, "dict"):
            serialized[interrupt_id] = response.dict()  # type: ignore[call-arg]
        elif isinstance(response, dict):
            serialized[interrupt_id] = response
        else:
            raise TypeError(
                "Unsupported HITL response type: "
                f"interrupt_id={interrupt_id} type={type(response)!r}"
            )

    return serialized


def summarize_hitl_response_map(hitl_response: Mapping[str, Any]) -> Dict[str, Any]:
    """Summarize a HITL response map for persistence.

    Returns:
        Dict with keys:
            - feedback_action: "APPROVED" if all decisions approve; else "DECLINED"
            - content: concatenated reject messages (may be empty)
            - interrupt_ids: list of interrupt ids present
    """

    interrupt_ids = list(hitl_response.keys())
    reject_messages: List[str] = []
    any_reject = False

    for interrupt_id, response in hitl_response.items():
        if hasattr(response, "decisions"):
            decisions = getattr(response, "decisions")
        elif isinstance(response, dict):
            decisions = response.get("decisions") or []
        else:
            raise TypeError(
                "Unsupported HITL response type: "
                f"interrupt_id={interrupt_id} type={type(response)!r}"
            )

        for decision in decisions:
            if hasattr(decision, "type"):
                decision_type = getattr(decision, "type")
                message = getattr(decision, "message", None)
            elif isinstance(decision, dict):
                decision_type = decision.get("type")
                message = decision.get("message")
            else:
                raise TypeError(
                    "Unsupported HITL decision type: "
                    f"interrupt_id={interrupt_id} type={type(decision)!r}"
                )

            if decision_type == "reject":
                any_reject = True
                if message:
                    msg = str(message).strip()
                    if msg:
                        reject_messages.append(msg)

    feedback_action = "DECLINED" if any_reject else "APPROVED"
    content = "\n".join(reject_messages) if reject_messages else ""

    return {
        "feedback_action": feedback_action,
        "content": content,
        "interrupt_ids": interrupt_ids,
    }


# =============================================================================
# Common Message Types
# =============================================================================

class ContentItem(BaseModel):
    type: str = Field(..., description="The type of content (text, image, etc.)")
    text: Optional[str] = Field(None, description="The text content if type is 'text'")
    image_url: Optional[str] = Field(
        None, description="The image URL if type is 'image'"
    )


class ChatMessage(BaseModel):
    role: str = Field(
        ..., description="The role of the message sender (user or assistant)"
    )
    content: Union[str, List[ContentItem]] = Field(
        ...,
        description="The content of the message, either a string or a list of content items",
    )


# =============================================================================
# Chat Request/Response Models
# =============================================================================

class ChatRequest(BaseModel):
    """Request model for streaming chat endpoint."""

    # Identity fields
    user_id: str = Field(
        default="test_user_001",
        description="User identifier"
    )
    conversation_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Conversation identifier - sessions are cached per conversation"
    )
    thread_id: str = Field(
        default="__default__",
        description="Thread identifier for checkpointing within a conversation"
    )

    # Messages
    messages: List[ChatMessage] = Field(
        default_factory=list,
        description="History of messages between the user and the assistant"
    )

    # Logging and tracking
    track_tokens: bool = Field(
        default=True,
        description="Whether to track token usage"
    )

    # Agent options
    subagents_enabled: Optional[List[str]] = Field(
        default=None,
        description="List of subagent names to enable (default: from config)"
    )
    background_auto_wait: Optional[bool] = Field(
        default=None,
        description="Whether to wait for background tasks (default: from config)"
    )
    plan_mode: bool = Field(
        default=False,
        description="When True, agent must submit a plan for approval via submit_plan tool before execution"
    )

    # Session management
    workspace_id: Optional[str] = Field(
        default=None,
        description="Workspace ID to use. Takes priority over conversation-based sessions."
    )
    sandbox_id: Optional[str] = Field(
        default=None,
        description="Existing sandbox ID to reconnect to (legacy, for direct sandbox access)"
    )

    # Interrupt/resume support (HITL)
    hitl_response: Optional[Dict[str, HITLResponse]] = Field(
        default=None,
        description="Structured HITL response: {interrupt_id: HITLResponse}. "
                    "Use this to respond to interrupt events with approve/reject decisions."
    )
    interrupt_feedback: Optional[str] = Field(
        default=None,
        description="[DEPRECATED] Use hitl_response instead. Legacy string feedback for plan review."
    )
    checkpoint_id: Optional[str] = Field(
        default=None,
        description="Specific checkpoint ID to resume from"
    )

    # Localization and context
    locale: Optional[str] = Field(
        default=None,
        description="Locale for output language, e.g., 'en-US' or 'zh-CN'"
    )
    timezone: Optional[str] = Field(
        default=None,
        description="IANA timezone identifier (e.g., 'America/New_York', 'Asia/Shanghai')"
    )

    # State restoration
    additional_context: Optional[List[LastThreadContext]] = Field(
        default=None,
        description="Additional context to be included. Supports: last_thread (state restoration)"
    )


class SessionInfo(BaseModel):
    """Information about a chat session."""

    conversation_id: str
    sandbox_id: Optional[str] = None
    initialized: bool = False
    last_active: Optional[str] = None
    mcp_servers_connected: int = 0


class StreamEvent(BaseModel):
    """Base model for SSE stream events."""

    event: str = Field(description="Event type (message_chunk, tool_calls, etc.)")
    data: dict = Field(description="Event payload")


class StatusResponse(BaseModel):
    """Response model for workflow status."""

    thread_id: str
    status: str = Field(description="Status: running, completed, failed, cancelled")
    conversation_id: Optional[str] = None
    sandbox_id: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Utility Request Models
# =============================================================================

class TTSRequest(BaseModel):
    text: str = Field(..., description="The text to convert to speech")
    voice_type: Optional[str] = Field(
        "BV700_V2_streaming", description="The voice type to use"
    )
    encoding: Optional[str] = Field("mp3", description="The audio encoding format")
    speed_ratio: Optional[float] = Field(1.0, description="Speech speed ratio")
    volume_ratio: Optional[float] = Field(1.0, description="Speech volume ratio")
    pitch_ratio: Optional[float] = Field(1.0, description="Speech pitch ratio")
    text_type: Optional[str] = Field("plain", description="Text type (plain or ssml)")
    with_frontend: Optional[int] = Field(
        1, description="Whether to use frontend processing"
    )
    frontend_type: Optional[str] = Field("unitTson", description="Frontend type")


class GeneratePodcastRequest(BaseModel):
    content: str = Field(..., description="The content of the podcast")


class WorkflowResumeRequest(BaseModel):
    """
    Request to resume workflow execution from a checkpoint.

    Note: This is deprecated. Use ChatRequest with interrupt_feedback instead.
    """

    checkpoint_id: Optional[str] = Field(
        None,
        description="Specific checkpoint ID to resume from (None = resume from latest)"
    )

    new_input: Optional[dict] = Field(
        None,
        description="Optional new state/messages to add before resuming execution"
    )

    retry_failed: bool = Field(
        False,
        description="Automatically retry from last checkpoint before failure"
    )

    max_retries: int = Field(
        3,
        ge=1,
        le=5,
        description="Maximum retry attempts for failed workflows (1-5)"
    )

    track_tokens: bool = Field(
        True,
        description="Track token usage and save execution logs"
    )


