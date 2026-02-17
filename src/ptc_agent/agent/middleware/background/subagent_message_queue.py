"""
Subagent Message Queue Middleware.

Checks Redis for follow-up messages queued by the orchestrator for running
subagents. Injected into subagent middleware stacks so that the main agent
can send additional instructions to a running subagent via
``Task(task_id="...", description="...")``.

Modeled on the main ``MessageQueueMiddleware`` but uses a per-task Redis key
(``subagent:queued_messages:{tool_call_id}``) instead of the per-thread key.
"""

import json
import logging
import time
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime

from langchain.agents.middleware.types import AgentMiddleware, AgentState

from ptc_agent.agent.middleware.background.middleware import current_background_tool_call_id
from ptc_agent.agent.middleware.background.registry import BackgroundTaskRegistry

logger = logging.getLogger(__name__)


class SubagentMessageQueueMiddleware(AgentMiddleware):
    """Checks Redis for follow-up messages queued for a running subagent.

    When the main agent calls ``Task(task_id="...", description="...")`` on a
    running subagent, the ``BackgroundSubagentMiddleware`` pushes the message
    to Redis.  This middleware picks it up before the subagent's next LLM call
    and injects it as a ``HumanMessage``.

    Placement: first item in ``subagent_middleware`` list so the follow-up
    is visible before any other middleware runs.
    """

    def __init__(self, registry: BackgroundTaskRegistry | None = None) -> None:
        super().__init__()
        self.registry = registry

    async def abefore_model(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """Check Redis for queued follow-up messages and inject before model call."""
        try:
            tool_call_id = current_background_tool_call_id.get()
            if not tool_call_id:
                return None

            from src.utils.cache.redis_cache import get_cache_client

            cache = get_cache_client()
            if not cache.enabled or not cache.client:
                return None

            key = f"subagent:queued_messages:{tool_call_id}"

            # Atomically read all queued messages and delete the key
            pipe = cache.client.pipeline()
            pipe.lrange(key, 0, -1)
            pipe.delete(key)
            results = await pipe.execute()

            raw_messages = results[0]
            if not raw_messages:
                return None

            # Parse queued messages
            queued: list[str] = []
            for raw in raw_messages:
                try:
                    data = json.loads(
                        raw.decode("utf-8") if isinstance(raw, bytes) else raw
                    )
                    queued.append(
                        data
                        if isinstance(data, str)
                        else data.get("content", str(data))
                    )
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning(
                        f"[SubagentMessageQueue] Failed to parse queued message: {e}"
                    )

            if not queued:
                return None

            content = "\n".join(queued) if len(queued) > 1 else queued[0]
            human_msg = HumanMessage(
                content=f"[Follow-up Instructions from Orchestrator]\n{content}"
            )

            logger.info(
                f"[SubagentMessageQueue] Injecting {len(queued)} follow-up message(s) "
                f"for tool_call_id={tool_call_id}"
            )

            # Emit SSE custom event so frontend can render the follow-up
            # in the subagent view as a user message
            event_data = {
                "type": "subagent_followup_injected",
                "tool_call_id": tool_call_id,
                "content": content,
                "count": len(queued),
                "timestamp": time.time(),
            }
            try:
                writer = get_stream_writer()
                writer(event_data)
            except Exception:
                pass

            # Capture for history replay so it appears when loading
            # subagent conversation from stored events
            if self.registry:
                try:
                    task = self.registry._tasks.get(tool_call_id)
                    agent_id = f"task:{task.task_id}" if task else f"subagent:{tool_call_id}"
                    await self.registry.append_captured_event(
                        tool_call_id,
                        {
                            "event": "subagent_followup_injected",
                            "data": {
                                "agent": agent_id,
                                "tool_call_id": tool_call_id,
                                "content": content,
                                "count": len(queued),
                                "timestamp": event_data["timestamp"],
                            },
                            "ts": event_data["timestamp"],
                        },
                    )
                except Exception:
                    pass

            return {"messages": [human_msg]}

        except Exception as e:
            logger.error(f"[SubagentMessageQueue] Error checking queue: {e}")
            return None
