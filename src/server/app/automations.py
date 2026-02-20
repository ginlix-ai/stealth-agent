"""
Automations API Router.

Provides REST endpoints for creating, managing, and monitoring
scheduled automations (cron and one-time triggers).

Endpoints (/api/v1/automations):
- POST   /automations                              - Create automation
- GET    /automations                              - List automations
- GET    /automations/{automation_id}              - Get automation
- PATCH  /automations/{automation_id}              - Update automation
- DELETE /automations/{automation_id}              - Delete automation
- POST   /automations/{automation_id}/trigger      - Manual trigger
- POST   /automations/{automation_id}/pause        - Pause
- POST   /automations/{automation_id}/resume       - Resume
- GET    /automations/{automation_id}/executions    - Execution history
"""

import logging

from fastapi import APIRouter, Query
from fastapi.responses import Response

from src.server.database import automation as auto_db
from src.server.handlers import automation_handler as handler
from src.server.models.automation import (
    AutomationCreate,
    AutomationExecutionResponse,
    AutomationExecutionsListResponse,
    AutomationResponse,
    AutomationsListResponse,
    AutomationUpdate,
)
from src.server.utils.api import CurrentUserId, handle_api_exceptions, raise_not_found

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Automations"])


# =============================================================================
# CRUD Endpoints
# =============================================================================


@router.post("/automations", response_model=AutomationResponse, status_code=201)
@handle_api_exceptions("create automation", logger, conflict_on_value_error=True)
async def create_automation(
    request: AutomationCreate,
    user_id: CurrentUserId,
):
    """Create a new scheduled automation."""
    automation = await handler.create_automation(
        user_id=user_id,
        data=request.model_dump(exclude_none=True),
    )
    return AutomationResponse.model_validate(automation)


@router.get("/automations", response_model=AutomationsListResponse)
@handle_api_exceptions("list automations", logger)
async def list_automations(
    user_id: CurrentUserId,
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List automations for the current user."""
    automations, total = await auto_db.list_automations(
        user_id, status=status, limit=limit, offset=offset,
    )
    return AutomationsListResponse(
        automations=[AutomationResponse.model_validate(a) for a in automations],
        total=total,
    )


@router.get("/automations/{automation_id}", response_model=AutomationResponse)
@handle_api_exceptions("get automation", logger)
async def get_automation(
    automation_id: str,
    user_id: CurrentUserId,
):
    """Get a specific automation."""
    automation = await auto_db.get_automation(automation_id, user_id)
    if not automation:
        raise_not_found("Automation")
    return AutomationResponse.model_validate(automation)


@router.patch("/automations/{automation_id}", response_model=AutomationResponse)
@handle_api_exceptions("update automation", logger, conflict_on_value_error=True)
async def update_automation(
    automation_id: str,
    request: AutomationUpdate,
    user_id: CurrentUserId,
):
    """Partial update of an automation."""
    automation = await handler.update_automation(
        automation_id=automation_id,
        user_id=user_id,
        data=request.model_dump(exclude_none=True),
    )
    if not automation:
        raise_not_found("Automation")
    return AutomationResponse.model_validate(automation)


@router.delete("/automations/{automation_id}", status_code=204)
@handle_api_exceptions("delete automation", logger)
async def delete_automation(
    automation_id: str,
    user_id: CurrentUserId,
):
    """Delete an automation (cascade deletes executions)."""
    deleted = await auto_db.delete_automation(automation_id, user_id)
    if not deleted:
        raise_not_found("Automation")
    return Response(status_code=204)


# =============================================================================
# Control Endpoints
# =============================================================================


@router.post("/automations/{automation_id}/trigger")
@handle_api_exceptions("trigger automation", logger, conflict_on_value_error=True)
async def trigger_automation(
    automation_id: str,
    user_id: CurrentUserId,
):
    """Manually trigger an automation immediately (doesn't affect next_run_at)."""
    result = await handler.trigger_automation(automation_id, user_id)
    return result


@router.post("/automations/{automation_id}/pause", response_model=AutomationResponse)
@handle_api_exceptions("pause automation", logger, conflict_on_value_error=True)
async def pause_automation(
    automation_id: str,
    user_id: CurrentUserId,
):
    """Pause an active automation."""
    automation = await handler.pause_automation(automation_id, user_id)
    if not automation:
        raise_not_found("Automation")
    return AutomationResponse.model_validate(automation)


@router.post("/automations/{automation_id}/resume", response_model=AutomationResponse)
@handle_api_exceptions("resume automation", logger, conflict_on_value_error=True)
async def resume_automation(
    automation_id: str,
    user_id: CurrentUserId,
):
    """Resume a paused or disabled automation."""
    automation = await handler.resume_automation(automation_id, user_id)
    if not automation:
        raise_not_found("Automation")
    return AutomationResponse.model_validate(automation)


# =============================================================================
# Execution History
# =============================================================================


@router.get(
    "/automations/{automation_id}/executions",
    response_model=AutomationExecutionsListResponse,
)
@handle_api_exceptions("list executions", logger)
async def list_executions(
    automation_id: str,
    user_id: CurrentUserId,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List execution history for an automation."""
    executions, total = await auto_db.list_executions(
        automation_id, user_id, limit=limit, offset=offset,
    )
    return AutomationExecutionsListResponse(
        executions=[
            AutomationExecutionResponse.model_validate(e) for e in executions
        ],
        total=total,
    )
