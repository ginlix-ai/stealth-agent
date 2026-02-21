"""
Automation tools for creating and managing scheduled automations.

These tools run on the HOST (not in sandbox) and have direct database access.
They allow the agent to create, inspect, and manage automations during conversations.

- check_automations: List all or inspect a specific automation + executions
- create_automation: Create a new scheduled automation (cron or one-time)
- manage_automation: Update, pause, resume, trigger, or delete automations
"""

import json
import logging
from datetime import datetime, timezone
from typing import Annotated, Any

from croniter import croniter
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from src.server.database import automation as auto_db
from src.server.handlers import automation_handler as auto_handler

logger = logging.getLogger(__name__)


# ==================== Helpers ====================


def _get_user_id(config: RunnableConfig) -> str:
    """Extract user_id from the runnable config."""
    configurable = config.get("configurable", {})
    user_id = configurable.get("user_id")
    if not user_id:
        raise ValueError("user_id not found in config.")
    return user_id


def _get_workspace_id(config: RunnableConfig) -> str | None:
    """Extract workspace_id from the runnable config."""
    configurable = config.get("configurable", {})
    return configurable.get("workspace_id")


def _get_timezone(config: RunnableConfig) -> str:
    """Extract user timezone from the runnable config, defaulting to UTC."""
    configurable = config.get("configurable", {})
    return configurable.get("timezone") or "UTC"


def _parse_schedule(schedule: str) -> dict[str, Any]:
    """Auto-detect cron vs one-time from schedule string.

    Returns:
        Dict with trigger_type and either cron_expression or next_run_at.

    Raises:
        ValueError: If schedule is neither valid cron nor valid ISO datetime.
    """
    try:
        croniter(schedule)
        return {"trigger_type": "cron", "cron_expression": schedule}
    except (ValueError, KeyError):
        try:
            dt = datetime.fromisoformat(schedule)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return {"trigger_type": "once", "next_run_at": dt}
        except ValueError:
            raise ValueError(
                f"Invalid schedule: '{schedule}'. "
                f"Use a cron expression (e.g. '0 9 * * 1-5') or "
                f"ISO datetime (e.g. '2026-03-01T10:00:00')."
            )


def _serialize(obj: Any) -> Any:
    """Convert non-serializable types (datetime, UUID) for clean LLM output."""
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "hex"):  # UUID
        return str(obj)
    return obj


# ==================== Tools ====================


@tool(response_format="content_and_artifact")
async def check_automations(
    config: RunnableConfig,
    automation_id: Annotated[
        str | None,
        "Automation ID to inspect. Omit to list all automations.",
    ] = None,
) -> tuple[str, dict]:
    """Check automations. Without an ID, lists all automations. With an ID, returns full details and recent execution history."""
    try:
        user_id = _get_user_id(config)

        if automation_id is None:
            automations, total = await auto_db.list_automations(user_id)
            result = _serialize(
                {
                    "automations": [
                        {
                            "automation_id": a["automation_id"],
                            "name": a["name"],
                            "status": a["status"],
                            "agent_mode": a["agent_mode"],
                            "schedule": a.get("cron_expression")
                            or (
                                a["next_run_at"].isoformat()
                                if a.get("next_run_at")
                                else None
                            ),
                            "next_run_at": a.get("next_run_at"),
                        }
                        for a in automations
                    ],
                    "total": total,
                }
            )
            artifact = _serialize(
                {
                    "type": "automations",
                    "mode": "list",
                    "automations": [
                        {
                            "automation_id": a["automation_id"],
                            "name": a["name"],
                            "status": a["status"],
                            "agent_mode": a["agent_mode"],
                            "schedule": a.get("cron_expression")
                            or (
                                a["next_run_at"].isoformat()
                                if a.get("next_run_at")
                                else None
                            ),
                            "next_run_at": a.get("next_run_at"),
                            "trigger_type": "cron"
                            if a.get("cron_expression")
                            else "once",
                        }
                        for a in automations
                    ],
                    "total": total,
                }
            )
            return json.dumps(result), artifact

        # Get details + last 5 executions
        automation = await auto_db.get_automation(automation_id, user_id)
        if not automation:
            return json.dumps({"error": f"Automation '{automation_id}' not found."}), {}

        executions, exec_total = await auto_db.list_executions(
            automation_id, user_id, limit=5
        )

        result = _serialize(
            {
                "automation": {
                    "automation_id": automation["automation_id"],
                    "name": automation["name"],
                    "description": automation.get("description"),
                    "instruction": automation["instruction"],
                    "trigger_type": automation["trigger_type"],
                    "schedule": automation.get("cron_expression")
                    or (
                        automation["next_run_at"].isoformat()
                        if automation.get("next_run_at")
                        else None
                    ),
                    "agent_mode": automation["agent_mode"],
                    "status": automation["status"],
                    "next_run_at": automation.get("next_run_at"),
                    "last_run_at": automation.get("last_run_at"),
                    "created_at": automation.get("created_at"),
                },
                "executions": [
                    {
                        "execution_id": e["automation_execution_id"],
                        "status": e["status"],
                        "scheduled_at": e.get("scheduled_at"),
                        "started_at": e.get("started_at"),
                        "completed_at": e.get("completed_at"),
                        "error_message": e.get("error_message"),
                    }
                    for e in executions
                ],
                "total_executions": exec_total,
            }
        )
        artifact = {
            "type": "automations",
            "mode": "detail",
            "automation": result["automation"],
            "executions": result["executions"],
            "total_executions": exec_total,
        }
        return json.dumps(result), artifact

    except Exception as e:
        logger.exception("[automation_tools] check_automations error")
        return json.dumps({"error": str(e)}), {}


@tool(response_format="content_and_artifact")
async def create_automation(
    name: Annotated[str, "Short name for the automation"],
    instruction: Annotated[str, "The prompt the agent will execute on each run"],
    schedule: Annotated[
        str,
        "Cron expression (e.g. '0 9 * * 1-5') for recurring, "
        "or ISO datetime (e.g. '2026-03-01T10:00:00') for one-time",
    ],
    config: RunnableConfig,
    description: Annotated[str | None, "Optional description"] = None,
    agent_mode: Annotated[
        str, "'flash' (fast, default) or 'ptc' (full sandbox)"
    ] = "flash",
) -> tuple[str, dict]:
    """Create a new scheduled automation."""
    try:
        user_id = _get_user_id(config)
        workspace_id = _get_workspace_id(config)
        tz = _get_timezone(config)

        # Parse schedule string into trigger_type + cron/datetime
        schedule_info = _parse_schedule(schedule)

        # Build creation data
        data: dict[str, Any] = {
            "name": name,
            "instruction": instruction,
            "description": description,
            "agent_mode": agent_mode,
            "timezone": tz,
            "workspace_id": workspace_id,
            "thread_strategy": "new",
            "max_failures": 3,
            **schedule_info,
        }

        automation = await auto_handler.create_automation(user_id, data)

        result = _serialize(
            {
                "success": True,
                "automation_id": automation["automation_id"],
                "name": automation["name"],
                "status": automation["status"],
                "trigger_type": automation["trigger_type"],
                "schedule": automation.get("cron_expression")
                or (
                    automation["next_run_at"].isoformat()
                    if automation.get("next_run_at")
                    else None
                ),
                "next_run_at": automation.get("next_run_at"),
            }
        )
        artifact = {
            "type": "automations",
            "mode": "created",
            "automation_id": result["automation_id"],
            "name": result["name"],
            "status": result["status"],
            "trigger_type": result["trigger_type"],
            "schedule": result["schedule"],
            "next_run_at": result["next_run_at"],
        }
        return json.dumps(result), artifact

    except ValueError as e:
        return json.dumps({"error": str(e)}), {}
    except Exception as e:
        logger.exception("[automation_tools] create_automation error")
        return json.dumps({"error": str(e)}), {}


@tool
async def manage_automation(
    automation_id: Annotated[str, "Automation ID to manage"],
    action: Annotated[
        str, "Action: 'update', 'pause', 'resume', 'trigger', or 'delete'"
    ],
    config: RunnableConfig,
    name: Annotated[str | None, "New name (action='update' only)"] = None,
    description: Annotated[str | None, "New description (action='update' only)"] = None,
    instruction: Annotated[
        str | None, "New instruction/prompt (action='update' only)"
    ] = None,
    schedule: Annotated[
        str | None, "New cron or ISO datetime schedule (action='update' only)"
    ] = None,
    agent_mode: Annotated[
        str | None,
        "New agent mode: 'flash' or 'ptc' (action='update' only)",
    ] = None,
) -> dict[str, Any]:
    """Manage an existing automation: update settings, pause, resume, trigger immediately, or delete."""
    try:
        user_id = _get_user_id(config)

        if action == "pause":
            result = await auto_handler.pause_automation(automation_id, user_id)
            if not result:
                return {"error": f"Automation '{automation_id}' not found."}
            return _serialize(
                {
                    "success": True,
                    "status": result["status"],
                }
            )

        elif action == "resume":
            result = await auto_handler.resume_automation(automation_id, user_id)
            if not result:
                return {"error": f"Automation '{automation_id}' not found."}
            return _serialize(
                {
                    "success": True,
                    "status": result["status"],
                    "next_run_at": result.get("next_run_at"),
                }
            )

        elif action == "trigger":
            result = await auto_handler.trigger_automation(automation_id, user_id)
            return _serialize(result)

        elif action == "delete":
            deleted = await auto_db.delete_automation(automation_id, user_id)
            if not deleted:
                return {"error": f"Automation '{automation_id}' not found."}
            return {"success": True, "deleted": automation_id}

        elif action == "update":
            update_data: dict[str, Any] = {}
            if name is not None:
                update_data["name"] = name
            if description is not None:
                update_data["description"] = description
            if instruction is not None:
                update_data["instruction"] = instruction
            if agent_mode is not None:
                update_data["agent_mode"] = agent_mode
            if schedule is not None:
                schedule_info = _parse_schedule(schedule)
                update_data.update(schedule_info)

            if not update_data:
                return {
                    "error": "No fields to update. Provide at least one of: "
                    "name, description, instruction, schedule, agent_mode."
                }

            result = await auto_handler.update_automation(
                automation_id, user_id, update_data
            )
            if not result:
                return {"error": f"Automation '{automation_id}' not found."}
            return _serialize(
                {
                    "success": True,
                    "automation_id": result["automation_id"],
                    "name": result["name"],
                    "status": result["status"],
                    "next_run_at": result.get("next_run_at"),
                }
            )

        else:
            return {
                "error": f"Unknown action: '{action}'. "
                f"Use 'update', 'pause', 'resume', 'trigger', or 'delete'."
            }

    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("[automation_tools] manage_automation error")
        return {"error": str(e)}
