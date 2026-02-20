"""
Request and response models for Automations API.

Defines Pydantic models for creating, updating, listing, and viewing
automations and their execution history.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Request Models
# =============================================================================


class AutomationCreate(BaseModel):
    """Request model for creating an automation."""

    name: str = Field(..., max_length=255, description="Display name for the automation")
    description: Optional[str] = Field(None, description="Optional description")

    # Trigger
    trigger_type: Literal["cron", "once"] = Field(
        ..., description="'cron' for recurring, 'once' for one-time"
    )
    cron_expression: Optional[str] = Field(
        None, description="Cron expression (required for trigger_type='cron')"
    )
    timezone: str = Field(
        default="UTC", description="IANA timezone (e.g., 'America/New_York')"
    )
    trigger_config: Optional[Dict[str, Any]] = Field(
        default=None, description="Future: event trigger parameters"
    )

    # Scheduling for one-time triggers
    next_run_at: Optional[datetime] = Field(
        None, description="Scheduled time for one-time triggers (UTC)"
    )

    # Agent config
    agent_mode: Literal["ptc", "flash"] = Field(
        default="flash", description="Agent mode for execution"
    )
    instruction: str = Field(
        ..., description="The prompt/instruction for the agent"
    )
    workspace_id: Optional[UUID] = Field(
        None, description="Workspace ID (required for 'ptc' mode)"
    )
    llm_model: Optional[str] = Field(
        None, description="LLM model name override"
    )
    additional_context: Optional[List[Dict[str, Any]]] = Field(
        None, description="Additional context items (skills, images, etc.)"
    )

    # Thread strategy
    thread_strategy: Literal["new", "continue"] = Field(
        default="new",
        description="'new' creates a fresh thread each run, 'continue' reuses a pinned thread",
    )
    conversation_thread_id: Optional[UUID] = Field(
        None, description="Pinned thread ID for 'continue' strategy"
    )

    # Lifecycle
    max_failures: int = Field(
        default=3, ge=1, le=100,
        description="Auto-disable after this many consecutive failures",
    )

    # Future extensibility
    delivery_config: Optional[Dict[str, Any]] = Field(
        default=None, description="Future: delivery method config"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Arbitrary metadata"
    )

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_if_needed(cls, v, info):
        # Actual cron validation done in handler (requires croniter import)
        return v


class AutomationUpdate(BaseModel):
    """Request model for partial update of an automation."""

    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None

    # Trigger
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    next_run_at: Optional[datetime] = None

    # Agent config
    agent_mode: Optional[Literal["ptc", "flash"]] = None
    instruction: Optional[str] = None
    workspace_id: Optional[UUID] = None
    llm_model: Optional[str] = None
    additional_context: Optional[List[Dict[str, Any]]] = None

    # Thread strategy
    thread_strategy: Optional[Literal["new", "continue"]] = None
    conversation_thread_id: Optional[UUID] = None

    # Lifecycle
    max_failures: Optional[int] = Field(None, ge=1, le=100)

    # Future
    delivery_config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


# =============================================================================
# Response Models
# =============================================================================


class AutomationResponse(BaseModel):
    """Response model for a single automation."""

    automation_id: UUID
    user_id: str
    name: str
    description: Optional[str] = None

    trigger_type: str
    cron_expression: Optional[str] = None
    timezone: str
    trigger_config: Optional[Dict[str, Any]] = None

    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None

    agent_mode: str
    instruction: str
    workspace_id: Optional[UUID] = None
    llm_model: Optional[str] = None
    additional_context: Optional[List[Dict[str, Any]]] = None

    thread_strategy: str
    conversation_thread_id: Optional[UUID] = None

    status: str
    max_failures: int
    failure_count: int

    delivery_config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AutomationsListResponse(BaseModel):
    """Response model for listing automations."""

    automations: List[AutomationResponse]
    total: int


class AutomationExecutionResponse(BaseModel):
    """Response model for a single automation execution."""

    automation_execution_id: UUID
    automation_id: UUID
    status: str
    conversation_thread_id: Optional[UUID] = None
    scheduled_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    server_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AutomationExecutionsListResponse(BaseModel):
    """Response model for listing automation executions."""

    executions: List[AutomationExecutionResponse]
    total: int
