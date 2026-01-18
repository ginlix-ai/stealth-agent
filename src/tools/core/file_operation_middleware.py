"""
File Operation Middleware for Real-Time SSE Event Emission.

This middleware intercepts write_file and edit_file tool calls to emit
file_operation events using LangGraph's custom event streaming API.

Architecture:
- Uses get_stream_writer() to emit custom events after tool execution
- Emits single "completed" event with full file content for frontend display
- Avoids state pollution - events go directly to stream, not agent context
- Works around limitation that tool Command updates don't reach stream_mode="updates"

Event Structure (ordered fields):
1. agent - Agent name (added by StreamingHandler)
2. operation - "write_file" or "edit_file"
3. file_path - Full path to the file
4. tool_call_id - Tool call identifier
5. timestamp - ISO format timestamp
6. status - "completed" or "failed"
7. line_count - Number of lines in content
8. content - Full file content (write_file only)
9. old_string - Original content (edit_file only)
10. new_string - Replacement content (edit_file only)
"""

import logging
from datetime import datetime, timezone
from typing import Annotated, Any, Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware, AgentState
from typing_extensions import NotRequired
from langgraph.config import get_stream_writer
from src.tools.core.filesystem import _file_operations_log_reducer

logger = logging.getLogger(__name__)


class FileOperationState(AgentState):
    """State schema for file operation middleware.

    Declares current_agent field so it propagates to request.state
    during tool execution, enabling agent name extraction in middleware.
    """
    current_agent: NotRequired[str] = "unknown"
    file_operations_log: Annotated[NotRequired[list[dict[str, Any]]], _file_operations_log_reducer]
    """Persistent audit trail of all file operations during workflow execution."""


class FileOperationMiddleware(AgentMiddleware):
    """
    Middleware that emits file_operation SSE events after tool execution.

    Hooks into tool execution to emit custom events with full file content
    for write_file and edit_file operations, enabling frontend to display
    file changes without polluting agent context.
    """

    # State schema declaration - makes current_agent accessible in request.state
    state_schema = FileOperationState

    # Tools to monitor for file operations
    MONITORED_TOOLS = {"write_file", "edit_file"}

    @staticmethod
    def _count_lines(text: str) -> int:
        """Count number of lines in text."""
        if not text:
            return 0
        return text.count('\n') + (1 if text and not text.endswith('\n') else 0)

    def _extract_agent_name_from_state(self, request: Any) -> str:
        """
        Extract agent name from graph state.

        The graph state contains a current_agent field that's set by routing
        functions (e.g., continue_to_running_research_team) before dispatching
        to each agent. This allows middleware to know which agent is currently running.

        Args:
            request: Tool call request which should have access to state

        Returns:
            Agent name from state, or "unknown" if not available
        """
        try:
            # Access state from request
            if hasattr(request, 'state') and isinstance(request.state, dict):
                current_agent = request.state.get('current_agent', '')

                if current_agent:
                    # Normalize to short name for SSE consistency
                    # "deep_research/coder" → "coder"
                    short_name = current_agent.split("/")[-1] if "/" in current_agent else current_agent
                    logger.debug(f"[AGENT_EXTRACT] from state.current_agent: {current_agent} → {short_name}")
                    return short_name
                else:
                    logger.debug("[AGENT_EXTRACT] current_agent field empty in state")
            else:
                logger.debug(f"[AGENT_EXTRACT] request.state not available or not dict. Has state: {hasattr(request, 'state')}")

        except Exception as e:
            logger.debug(f"[AGENT_EXTRACT] Failed to extract from state: {e}")

        logger.warning("[AGENT_EXTRACT] Could not extract agent from state - returning 'unknown'")
        return "unknown"

    async def awrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """
        Intercept tool calls and emit file operation events after execution.

        Emits a single event per operation with full content for frontend display.
        Event field order: agent, operation, file_path, tool_call_id, timestamp,
        status, line_count, content/old_string/new_string.

        Args:
            request: Tool call request with tool_call dict containing name, args, id
            handler: Next handler in chain (actual tool execution)

        Returns:
            Tool execution result
        """
        tool_call = request.tool_call
        tool_name = tool_call.get("name")

        # Only process file operation tools
        if tool_name not in self.MONITORED_TOOLS:
            return await handler(request)

        tool_call_id = tool_call.get("id", "unknown")
        tool_args = tool_call.get("args", {})
        file_path = tool_args.get("file_path", "unknown")

        logger.debug(f"[FILE_OP_MIDDLEWARE] Intercepting {tool_name} (id: {tool_call_id})")

        # Extract agent name from graph state
        agent_name = self._extract_agent_name_from_state(request)

        # Get stream writer for custom event emission
        try:
            writer = get_stream_writer()
        except Exception as e:
            logger.error(f"[FILE_OP_MIDDLEWARE] Failed to get stream writer: {e}")
            # Continue with tool execution even if streaming fails
            return await handler(request)

        # Execute the actual tool
        try:
            result = await handler(request)

            # Build completed event with ordered fields
            # Include agent name from request context
            timestamp = datetime.now(timezone.utc).isoformat()

            completed_event = {
                "agent": agent_name,  # Include agent name from request
                "operation": tool_name,
                "file_path": file_path,
                "tool_call_id": tool_call_id,
                "timestamp": timestamp,
                "status": "completed",
            }

            # Add operation-specific content with line count
            if tool_name == "write_file":
                content = tool_args.get("content", "")
                completed_event["line_count"] = self._count_lines(content)
                completed_event["content"] = content

            elif tool_name == "edit_file":
                old_string = tool_args.get("old_string", "")
                new_string = tool_args.get("new_string", "")
                completed_event["line_count"] = self._count_lines(new_string)
                completed_event["old_string"] = old_string
                completed_event["new_string"] = new_string

            try:
                writer(completed_event)
                logger.debug(
                    f"[FILE_OP_MIDDLEWARE] ✓ Emitted completed event: {file_path} "
                    f"({completed_event.get('line_count', 0)} lines)"
                )
            except Exception as e:
                logger.error(f"[FILE_OP_MIDDLEWARE] Failed to emit completed event: {e}")

            return result

        except Exception as e:
            # Emit "failed" event on error
            logger.error(f"[FILE_OP_MIDDLEWARE] Tool execution failed: {e}")

            failed_timestamp = datetime.now(timezone.utc).isoformat()
            failed_event = {
                "agent": agent_name,  # Include agent name from request
                "operation": tool_name,
                "file_path": file_path,
                "tool_call_id": tool_call_id,
                "timestamp": failed_timestamp,
                "status": "failed",
                "error": str(e),
            }

            try:
                writer(failed_event)
                logger.debug(f"[FILE_OP_MIDDLEWARE] ✓ Emitted failed event: {file_path}")
            except Exception as emit_error:
                logger.error(f"[FILE_OP_MIDDLEWARE] Failed to emit failed event: {emit_error}")

            # Re-raise to preserve error handling
            raise
