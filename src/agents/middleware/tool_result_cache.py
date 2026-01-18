"""
Generic Tool Result Cache Middleware

Automatically caches specified tool results to configured cache files with SSE event emission.
Replaces manual cache file creation and provides flexible, reusable caching for any tool set.
"""

from langgraph.config import get_stream_writer
from datetime import datetime, timezone
from langchain.agents.middleware import AgentMiddleware, AgentState
from typing_extensions import NotRequired
from langgraph.types import Command
import logging

logger = logging.getLogger(__name__)


class ToolResultCacheState(AgentState):
    """State schema for accessing current_agent field."""
    current_agent: NotRequired[str] = "unknown"


class ToolResultCacheMiddleware(AgentMiddleware):
    """
    Generic middleware for automatically caching tool results to filesystem.

    This middleware intercepts specified tool calls and appends their results
    to a configured cache file. SSE events are emitted to match actual agent behavior
    (write_file for first creation, edit_file for subsequent appends).

    Features:
    - Configurable tool monitoring
    - Configurable cache file path
    - Optional agent type filtering
    - Automatic SSE event emission
    - Non-fatal error handling

    Example Usage:
        # Cache data retrieval tools
        data_cache = ToolResultCacheMiddleware(
            monitored_tools={"get_stock_daily_prices", "get_company_overview"},
            cache_file_path="/data/raw.md",
            agent_types={"deep_research/data_agent"},
            cache_header="# Data Agent Tool Call Cache"
        )

        # Cache analysis tools
        analyze_cache = ToolResultCacheMiddleware(
            monitored_tools={"technical_analyze", "financial_analyze"},
            cache_file_path="/data/analysis.md",
            agent_types={"deep_research/coder"},
            cache_header="# Analysis Tool Result Cache"
        )
    """

    state_schema = ToolResultCacheState

    def __init__(
        self,
        monitored_tools: set[str],
        cache_file_path: str,
        agent_types: set[str] | None = None,
        cache_header: str | None = None,
    ):
        """
        Initialize the generic tool result cache middleware.

        Args:
            monitored_tools: Set of tool names to intercept and cache
            cache_file_path: Path where cache file should be stored (e.g., "/data/raw.md")
            agent_types: Optional set of agent type identifiers to filter by
                        (e.g., {"deep_research/data_agent"}). If None, applies to all agents.
            cache_header: Optional header text for new cache files (default: "# Tool Result Cache")
        """
        super().__init__()
        self.monitored_tools = monitored_tools
        self.cache_file_path = cache_file_path
        self.agent_types = agent_types
        self.cache_header = cache_header or "# Tool Result Cache"

        # Logging prefix based on cache file
        self.log_prefix = f"[{cache_file_path.upper().replace('/', '_')}]"

        # Track cache state within agent execution
        # LangGraph batches Command updates - they're applied AFTER the agent step completes,
        # not between tool calls. This local cache ensures subsequent tool calls in the same
        # agent step see updates from previous calls.
        self._local_cache: dict | None = None

    async def awrap_tool_call(self, request, handler):
        """
        Intercept monitored tool calls and append results to cache file.

        Args:
            request: Tool call request with tool_call, state
            handler: Next handler in middleware chain

        Returns:
            Command with updated messages and files state, or original ToolMessage
        """
        tool_call = request.tool_call
        tool_name = tool_call.get("name")

        # Only process monitored tools
        if tool_name not in self.monitored_tools:
            return await handler(request)

        # Check agent type filter if configured
        if self.agent_types is not None:
            current_agent_type = request.state.get("current_agent", "")
            if current_agent_type not in self.agent_types:
                logger.debug(
                    f"{self.log_prefix} Skipping {tool_name} - agent type {current_agent_type} not in filter"
                )
                return await handler(request)

        # Execute tool
        result = await handler(request)

        # Extract context from state
        state = request.state
        agent_name = self._extract_agent_name(request)
        tool_call_id = tool_call.get("id", "unknown")

        # Get stream writer for SSE events
        try:
            writer = get_stream_writer()
        except Exception as e:
            logger.error(f"{self.log_prefix} Failed to get stream writer: {e}")
            writer = None

        try:
            # Read existing cache file from state first (authoritative for cross-step updates)
            # Then fall back to local cache (for same-step updates within batched Commands)
            existing_files = state.get("files", {})
            existing_cache = existing_files.get(self.cache_file_path)
            if existing_cache is None:
                # File not in state - might have been created earlier in this agent step
                existing_cache = self._local_cache

            # Build cache entry for this tool call
            cache_entry_lines = self._format_cache_entry(result.content)

            # Determine operation type and build content
            if existing_cache:
                # File exists - append new entry (emit edit_file event)
                old_content_lines = existing_cache["content"]
                new_content_lines = old_content_lines + cache_entry_lines

                operation = "edit_file"
                old_string = "".join(old_content_lines)
                new_string = "".join(new_content_lines)
                created_at = existing_cache.get("created_at")
                modified_at = datetime.now(timezone.utc).isoformat()
            else:
                # File doesn't exist - create new (emit write_file event)
                header = [f"{self.cache_header}\n", "\n"]
                new_content_lines = header + cache_entry_lines

                operation = "write_file"
                old_string = None
                new_string = "".join(new_content_lines)
                created_at = modified_at = datetime.now(timezone.utc).isoformat()

            # Create FileData structure
            updated_file_data = {
                "content": new_content_lines,
                "path": self.cache_file_path,
                "created_at": created_at,
                "modified_at": modified_at
            }

            # Update local cache for subsequent tool calls in the same agent step
            self._local_cache = updated_file_data

            # Emit file_operation SSE event (matching actual agent behavior)
            if writer:
                file_event = {
                    "agent": agent_name,
                    "operation": operation,  # "write_file" or "edit_file"
                    "file_path": self.cache_file_path,
                    "tool_call_id": tool_call_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "completed",
                    "line_count": len(cache_entry_lines),
                }

                # Add operation-specific fields
                if operation == "write_file":
                    file_event["content"] = new_string
                elif operation == "edit_file":
                    file_event["old_string"] = old_string
                    file_event["new_string"] = new_string

                writer(file_event)

            logger.debug(
                f"{self.log_prefix} Cached {tool_name} result ({len(cache_entry_lines)} lines)"
            )

            # Return Command with file update
            # Note: file_operations_log is for DB persistence
            # SSE emission is already handled by writer() above, so pending_file_events is not needed
            return Command(
                update={
                    "messages": [result],
                    "files": {self.cache_file_path: updated_file_data},
                    "file_operations_log": [file_event],  # For database persistence
                }
            )

        except Exception as e:
            logger.error(f"{self.log_prefix} Failed to cache tool result: {e}", exc_info=True)

            # Emit failed event
            if writer:
                error_event = {
                    "agent": agent_name,
                    "operation": "edit_file",  # Use edit_file for consistency
                    "file_path": self.cache_file_path,
                    "tool_call_id": tool_call_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "failed",
                    "error": str(e),
                }
                writer(error_event)

            # Return original result (non-fatal - don't break workflow)
            return result

    def _format_cache_entry(self, tool_result: str) -> list[str]:
        """
        Format cache entry as markdown lines.

        Tools are expected to return file-ready formatted output with descriptive headers
        and metadata. This method just adds a separator and appends the result.

        Args:
            tool_result: Tool result content (file-ready markdown with headers)

        Returns:
            List of markdown lines to append to cache file
        """
        lines = [
            "---\n",
            "\n",
            f"{tool_result}\n",
            "\n",
        ]

        return lines

    def _extract_agent_name(self, request) -> str:
        """
        Extract current agent name from request state.

        Args:
            request: Tool call request with state attribute

        Returns:
            Agent name string, defaults to "unknown" if not found
        """
        try:
            if hasattr(request, 'state') and isinstance(request.state, dict):
                current_agent = request.state.get('current_agent', '')
                if current_agent:
                    # Normalize to short name for SSE consistency
                    # "deep_research/coder" → "coder"
                    short_name = current_agent.split("/")[-1] if "/" in current_agent else current_agent
                    return short_name
        except Exception as e:
            logger.debug(f"{self.log_prefix} Agent extraction failed: {e}")

        return "unknown"
