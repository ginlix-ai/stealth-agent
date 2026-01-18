"""
PTC Graph Builder - Build per-conversation LangGraph graphs.

This module creates LangGraph-compatible graphs for the PTC agent,
with per-conversation sandbox sessions (unlike graph.py which uses
a global shared session).
"""

import asyncio
import logging
from typing import Any


from ptc_agent import PTCAgent
from ptc_agent.config import AgentConfig
from ptc_agent.core.session import Session

from src.server.services.session_manager import SessionService

logger = logging.getLogger(__name__)


async def build_ptc_graph(
    conversation_id: str,
    config: AgentConfig,
    subagent_names: list[str] | None = None,
    sandbox_id: str | None = None,
    operation_callback: Any | None = None,
    checkpointer: Any | None = None,
) -> Any:
    """
    Build a compiled LangGraph for a specific conversation.

    This creates a per-conversation sandbox session and wraps the PTCAgent
    in a LangGraph-compatible graph structure.

    Args:
        conversation_id: Unique conversation identifier for session management
        config: AgentConfig with LLM and tool configuration
        subagent_names: Optional list of subagent names to enable
        sandbox_id: Optional specific sandbox ID to use (for reconnecting to existing sandbox)
        operation_callback: Optional callback for file operation logging
        checkpointer: Optional LangGraph checkpointer for state persistence (e.g., AsyncPostgresSaver)

    Returns:
        Compiled StateGraph compatible with WorkflowStreamHandler

    Example:
        ptc_graph = await build_ptc_graph("conv-123", setup.ptc_config, checkpointer=checkpointer)
        async for event in handler.stream_workflow(ptc_graph, input_state, config):
            yield event
    """
    logger.info(f"Building PTC graph for conversation: {conversation_id}")

    # Get session service instance
    session_service = SessionService.get_instance()
    session = await session_service.get_or_create_session(
        conversation_id=conversation_id,
        sandbox_id=sandbox_id,
    )

    if not session.sandbox or not session.mcp_registry:
        raise RuntimeError(
            f"Failed to initialize session for conversation {conversation_id}"
        )

    # Create PTCAgent instance (blocking I/O wrapped in thread)
    ptc_agent = await asyncio.to_thread(PTCAgent, config)

    # Create the inner agent with conversation-specific sandbox.
    # IMPORTANT: pass the server checkpointer into the deepagent so that partial
    # progress (tools, intermediate messages, etc.) is checkpointed frequently.
    inner_agent = ptc_agent.create_agent(
        sandbox=session.sandbox,
        mcp_registry=session.mcp_registry,
        subagent_names=subagent_names or config.subagents_enabled,
        operation_callback=operation_callback,
        checkpointer=checkpointer,
    )

    logger.info(
        f"Created PTC agent for {conversation_id} with "
        f"subagents: {subagent_names or config.subagents_enabled} "
        f"(checkpointer={'enabled' if checkpointer else 'disabled'})"
    )

    # Return the deepagent/orchestrator directly.
    # It supports .astream/.ainvoke/.aget_state and will persist state via checkpointer.
    return inner_agent


async def build_ptc_graph_with_session(
    session: Session,
    config: AgentConfig,
    subagent_names: list[str] | None = None,
    operation_callback: Any | None = None,
    checkpointer: Any | None = None,
) -> Any:
    """
    Build a compiled LangGraph using a provided session.

    This is used for workspace-based requests where the session is
    managed by WorkspaceManager instead of SessionService.

    Args:
        session: Pre-initialized Session with sandbox and MCP registry
        config: AgentConfig with LLM and tool configuration
        subagent_names: Optional list of subagent names to enable
        operation_callback: Optional callback for file operation logging
        checkpointer: Optional LangGraph checkpointer for state persistence (e.g., AsyncPostgresSaver)

    Returns:
        Compiled StateGraph compatible with WorkflowStreamHandler

    Example:
        session = await workspace_manager.get_session_for_workspace(workspace_id)
        ptc_graph = await build_ptc_graph_with_session(session, config, checkpointer=checkpointer)
        async for event in handler.stream_workflow(ptc_graph, input_state, config):
            yield event
    """
    workspace_id = session.conversation_id
    logger.info(f"Building PTC graph with session for workspace: {workspace_id}")

    if not session.sandbox or not session.mcp_registry:
        raise RuntimeError(
            f"Session for workspace {workspace_id} is not properly initialized"
        )

    # Create PTCAgent instance (blocking I/O wrapped in thread)
    ptc_agent = await asyncio.to_thread(PTCAgent, config)

    # Create the inner agent with the session's sandbox.
    # IMPORTANT: pass the server checkpointer into the deepagent so that partial
    # progress (tools, intermediate messages, etc.) is checkpointed frequently.
    inner_agent = ptc_agent.create_agent(
        sandbox=session.sandbox,
        mcp_registry=session.mcp_registry,
        subagent_names=subagent_names or config.subagents_enabled,
        operation_callback=operation_callback,
        checkpointer=checkpointer,
    )

    logger.info(
        f"Created PTC agent for workspace {workspace_id} with "
        f"subagents: {subagent_names or config.subagents_enabled} "
        f"(checkpointer={'enabled' if checkpointer else 'disabled'})"
    )

    # Return the deepagent/orchestrator directly.
    # It supports .astream/.ainvoke/.aget_state and will persist state via checkpointer.
    return inner_agent
