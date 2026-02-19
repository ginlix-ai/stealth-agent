"""Tool call counter middleware for tracking subagent tool usage.

This middleware is injected into subagents to count their tool calls and
report metrics back to the BackgroundTaskRegistry.

It also emits a `subagent_identity` custom stream event on the first model
call so the streaming handler can map LangGraph namespace UUIDs to our
stable background task identities.
"""

import time
from collections.abc import Awaitable, Callable

import structlog
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from ptc_agent.agent.middleware.background.middleware import current_background_tool_call_id
from ptc_agent.agent.middleware.background.registry import BackgroundTaskRegistry

logger = structlog.get_logger(__name__)


class ToolCallCounterMiddleware(AgentMiddleware):
    """Middleware to count tool calls and report to BackgroundTaskRegistry.

    This middleware is designed to be injected into subagents running in the
    background. It tracks how many tool calls each subagent makes and what
    tools are being used.

    It also emits a ``subagent_identity`` custom stream event on the first
    model call.  The streaming handler receives this event *with* the
    LangGraph namespace tuple attached, which lets it register the mapping
    from opaque ``tools:<uuid>`` namespace to our stable ``agent_id``.

    The middleware uses a contextvar (current_background_tool_call_id) to identify
    which background task it belongs to. Contextvars properly propagate across
    await boundaries, ensuring tool calls are tracked even when subagents
    execute in different execution contexts.

    Usage:
        # Create counter middleware with shared registry
        counter = ToolCallCounterMiddleware(registry=background_middleware.registry)

        # Inject into subagent specs
        subagent_spec["middleware"] = [counter]
    """

    def __init__(self, registry: BackgroundTaskRegistry) -> None:
        """Initialize the counter middleware.

        Args:
            registry: The BackgroundTaskRegistry to report metrics to
        """
        super().__init__()
        self.tools = []  # No additional tools
        self.registry = registry
        self._emitted_identity: set[str] = (
            set()
        )  # task_ids that already emitted identity event

    def clear_identity(self, tool_call_id: str) -> None:
        """Remove a tool_call_id from the emitted identity set.

        Called when resuming a completed subagent so that the
        ``subagent_identity`` event is re-emitted on the resumed
        invocation's first model call, allowing the streaming handler
        to register new namespace UUID mappings.

        Args:
            tool_call_id: The tool_call_id to clear
        """
        self._emitted_identity.discard(tool_call_id)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Emit subagent_identity stream event on first model call.

        This runs BEFORE the LLM generates any output, so the streaming
        handler can register the namespace mapping before any message_chunk
        or tool_call_chunks events arrive.

        The custom event carries ``tool_call_id``; the streaming infrastructure
        automatically attaches the correct ``namespace_tuple`` so the handler
        knows which LangGraph namespace UUID maps to which background task.
        """
        tool_call_id = current_background_tool_call_id.get()

        if tool_call_id and self.registry and tool_call_id not in self._emitted_identity:
            try:
                from langgraph.config import get_stream_writer

                writer = get_stream_writer()
                writer({"type": "subagent_identity", "tool_call_id": tool_call_id})
                self._emitted_identity.add(tool_call_id)
                logger.debug(
                    "Emitted subagent_identity event",
                    tool_call_id=tool_call_id,
                )
            except Exception as e:
                logger.debug(
                    "Failed to emit subagent_identity event",
                    tool_call_id=tool_call_id,
                    error=str(e),
                )

        response = await handler(request)

        # Capture events for post-interrupt persistence
        tool_call_id = current_background_tool_call_id.get()
        if tool_call_id and self.registry:
            try:
                ai_msg = response.result[0] if response.result else None
                if ai_msg:
                    from src.llms.content_utils import format_llm_content

                    formatted = format_llm_content(ai_msg.content)
                    tool_calls = getattr(ai_msg, "tool_calls", None) or []
                    agent_id = self._get_agent_id(tool_call_id)
                    msg_id = getattr(ai_msg, "id", f"msg-{tool_call_id}")

                    # Emit reasoning with start/complete signals so frontend
                    # can initialize currentReasoningIdRef properly
                    if formatted.get("reasoning"):
                        await self.registry.append_captured_event(
                            tool_call_id,
                            {
                                "event": "message_chunk",
                                "data": {
                                    "agent": agent_id,
                                    "id": msg_id,
                                    "role": "assistant",
                                    "content": "start",
                                    "content_type": "reasoning_signal",
                                },
                                "ts": time.time(),
                            },
                        )
                        await self.registry.append_captured_event(
                            tool_call_id,
                            {
                                "event": "message_chunk",
                                "data": {
                                    "agent": agent_id,
                                    "id": msg_id,
                                    "role": "assistant",
                                    "content": formatted["reasoning"],
                                    "content_type": "reasoning",
                                    "finish_reason": None,
                                },
                                "ts": time.time(),
                            },
                        )
                        await self.registry.append_captured_event(
                            tool_call_id,
                            {
                                "event": "message_chunk",
                                "data": {
                                    "agent": agent_id,
                                    "id": msg_id,
                                    "role": "assistant",
                                    "content": "complete",
                                    "content_type": "reasoning_signal",
                                },
                                "ts": time.time(),
                            },
                        )

                    # Emit text chunk if present
                    if formatted.get("text"):
                        await self.registry.append_captured_event(
                            tool_call_id,
                            {
                                "event": "message_chunk",
                                "data": {
                                    "agent": agent_id,
                                    "id": msg_id,
                                    "role": "assistant",
                                    "content": formatted["text"],
                                    "content_type": "text",
                                    "finish_reason": "tool_calls"
                                    if tool_calls
                                    else "stop",
                                },
                                "ts": time.time(),
                            },
                        )

                    if tool_calls:
                        await self.registry.append_captured_event(
                            tool_call_id,
                            {
                                "event": "tool_calls",
                                "data": {
                                    "agent": agent_id,
                                    "id": msg_id,
                                    "role": "assistant",
                                    "tool_calls": [
                                        {
                                            "name": tc["name"],
                                            "args": tc.get("args", {}),
                                            "id": tc["id"],
                                            "type": "tool_call",
                                        }
                                        for tc in tool_calls
                                    ],
                                    "finish_reason": "tool_calls",
                                },
                                "ts": time.time(),
                            },
                        )
            except Exception:
                pass  # Never break the agent for capture failures

        return response

    def _get_agent_id(self, tool_call_id: str) -> str:
        """Resolve agent identifier in task:{task_id} format."""
        task = self.registry._tasks.get(tool_call_id)
        return f"task:{task.task_id}" if task else f"subagent:{tool_call_id}"

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """Synchronous wrap_tool_call - no tracking in sync mode."""
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Count tool call and report to registry.

        This method:
        1. Extracts the tool name from the request
        2. Gets the task_id from the asyncio task context
        3. Reports the metric to the registry
        4. Executes the tool call
        """
        # Extract tool name
        tool_call = request.tool_call
        tool_name = tool_call.get("name", "unknown")

        # Get tool_call_id from contextvar (set by BackgroundSubagentMiddleware)
        # Contextvars properly propagate across await boundaries
        tool_call_id = current_background_tool_call_id.get()

        # Report metric to registry before execution
        if tool_call_id and self.registry:
            await self.registry.update_metrics(tool_call_id, tool_name)
            logger.debug(
                "Counted tool call for background task",
                tool_call_id=tool_call_id,
                tool_name=tool_name,
            )

        # Execute the tool call
        result = await handler(request)

        # Capture tool_call_result for post-interrupt persistence
        tool_call_id = current_background_tool_call_id.get()
        if tool_call_id and self.registry:
            try:
                agent_id = self._get_agent_id(tool_call_id)
                if isinstance(result, ToolMessage):
                    content = (
                        result.content
                        if isinstance(result.content, str)
                        else str(result.content)
                    )
                    await self.registry.append_captured_event(
                        tool_call_id,
                        {
                            "event": "tool_call_result",
                            "data": {
                                "agent": agent_id,
                                "id": getattr(result, "id", ""),
                                "role": "assistant",
                                "tool_call_id": result.tool_call_id,
                                "content": content[:4096],
                                "content_type": "text",
                            },
                            "ts": time.time(),
                        },
                    )
                elif isinstance(result, Command):
                    msgs = (result.update or {}).get("messages", [])
                    for msg in msgs:
                        if isinstance(msg, ToolMessage):
                            content = (
                                msg.content
                                if isinstance(msg.content, str)
                                else str(msg.content)
                            )
                            await self.registry.append_captured_event(
                                tool_call_id,
                                {
                                    "event": "tool_call_result",
                                    "data": {
                                        "agent": agent_id,
                                        "id": getattr(msg, "id", ""),
                                        "role": "assistant",
                                        "tool_call_id": msg.tool_call_id,
                                        "content": content[:4096],
                                        "content_type": "text",
                                    },
                                    "ts": time.time(),
                                },
                            )
            except Exception:
                pass  # Never break the agent for capture failures

        return result
