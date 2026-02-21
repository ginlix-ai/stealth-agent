"""
HITL onboarding tools: create_workspace and start_question.

These tools use interrupt() to pause the graph and wait for user approval
via the frontend, following the same pattern as AskUserQuestion.
"""

import json
import logging
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.types import Command, interrupt

try:
    from langchain.tools import InjectedToolCallId
except ImportError:
    from langchain_core.tools import InjectedToolCallId

logger = logging.getLogger(__name__)


@tool("create_workspace")
async def create_workspace(
    name: str,
    description: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> Command:
    """Create a new workspace for the user and wait for their approval.

    Use this after onboarding is complete to set up the user's first workspace.
    The user will see a card with the workspace name and description, and can
    approve or decline the creation.

    Args:
        name: Name for the new workspace (e.g. "My Portfolio Analysis")
        description: Brief description of the workspace purpose
    """
    # Pause graph — frontend shows CreateWorkspaceCard
    response = interrupt(
        {
            "action_requests": [
                {
                    "type": "create_workspace",
                    "workspace_name": name,
                    "workspace_description": description,
                }
            ]
        }
    )

    # Parse hitl_response: {"decisions": [{"type": "approve"|"reject", ...}]}
    approved = False
    if isinstance(response, dict):
        decisions = response.get("decisions", [])
        if decisions and decisions[0].get("type") == "approve":
            approved = True

    if not approved:
        content = "User declined workspace creation."
        return Command(
            update={
                "messages": [
                    ToolMessage(content=content, tool_call_id=tool_call_id),
                ],
            }
        )

    # Create the workspace
    try:
        from src.server.services.workspace_manager import WorkspaceManager

        configurable = config.get("configurable", {})
        user_id = configurable.get("user_id")
        if not user_id:
            raise ValueError("user_id not found in config")

        workspace_manager = WorkspaceManager.get_instance()
        workspace = await workspace_manager.create_workspace(
            user_id=user_id,
            name=name,
            description=description,
        )

        workspace_id = str(workspace["workspace_id"])
        content = json.dumps(
            {
                "success": True,
                "workspace_id": workspace_id,
                "workspace_name": name,
            }
        )
    except Exception as e:
        logger.error(f"Failed to create workspace: {e}")
        content = json.dumps({"success": False, "error": str(e)})

    return Command(
        update={
            "messages": [
                ToolMessage(content=content, tool_call_id=tool_call_id),
            ],
        }
    )


@tool("start_question")
async def start_question(
    workspace_id: str,
    question: str,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> Command:
    """Start a question in a workspace, prompting the user to navigate there.

    Use this after creating a workspace to suggest an initial question for
    the user to explore. The user will see the question and can approve to
    navigate to the workspace with the question auto-sent.

    Args:
        workspace_id: The workspace ID to start the question in
        question: The question to ask (should be actionable and related to user interests)
    """
    # Pause graph — frontend shows StartQuestionCard
    response = interrupt(
        {
            "action_requests": [
                {
                    "type": "start_question",
                    "workspace_id": workspace_id,
                    "question": question,
                }
            ]
        }
    )

    # Parse hitl_response
    approved = False
    if isinstance(response, dict):
        decisions = response.get("decisions", [])
        if decisions and decisions[0].get("type") == "approve":
            approved = True

    if not approved:
        content = "User declined starting the question."
        return Command(
            update={
                "messages": [
                    ToolMessage(content=content, tool_call_id=tool_call_id),
                ],
            }
        )

    # No server-side work — frontend handles navigation + auto-send
    content = json.dumps(
        {
            "success": True,
            "workspace_id": workspace_id,
            "question": question,
            "action": "navigate_to_workspace",
        }
    )

    return Command(
        update={
            "messages": [
                ToolMessage(content=content, tool_call_id=tool_call_id),
            ],
        }
    )
