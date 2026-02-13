"""
Message Queue Middleware.

Checks Redis for queued user messages before each LLM call and injects them
into the conversation state. This enables users to send messages while the
agent is processing, which get picked up before the next model invocation.
"""

import json
import logging
import time
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.config import get_config, get_stream_writer
from langgraph.runtime import Runtime

from langchain.agents.middleware.types import AgentMiddleware, AgentState

logger = logging.getLogger(__name__)


class MessageQueueMiddleware(AgentMiddleware):
    """Checks Redis for queued user messages before each LLM call.

    When a user sends a message while the agent is already processing,
    the server queues it in Redis. This middleware picks up those queued
    messages before the next LLM invocation and injects them as a
    HumanMessage into the conversation state.

    Placement: main_only_middleware (subagents don't consume queued messages).
    """

    async def abefore_model(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """Check Redis for queued messages and inject them before model call."""
        try:
            config = get_config()
            thread_id = config.get("configurable", {}).get("thread_id")
            if not thread_id:
                return None

            # Import here to avoid circular imports
            from src.utils.cache.redis_cache import get_cache_client

            cache = get_cache_client()
            if not cache.enabled or not cache.client:
                return None

            key = f"workflow:queued_messages:{thread_id}"

            # Atomically read all queued messages and delete the key
            pipe = cache.client.pipeline()
            pipe.lrange(key, 0, -1)
            pipe.delete(key)
            results = await pipe.execute()

            raw_messages = results[0]
            if not raw_messages:
                return None

            # Parse queued messages
            queued = []
            for raw in raw_messages:
                try:
                    data = json.loads(
                        raw.decode("utf-8") if isinstance(raw, bytes) else raw
                    )
                    queued.append(data)
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning(f"[MessageQueue] Failed to parse queued message: {e}")

            if not queued:
                return None

            # Build combined message content
            if len(queued) == 1:
                content = queued[0]["content"]
            else:
                lines = [
                    f"{i + 1}. {msg['content']}" for i, msg in enumerate(queued)
                ]
                content = "\n".join(lines)

            human_msg = HumanMessage(
                content=f"[Queued Message from User]\n{content}"
            )

            logger.info(
                f"[MessageQueue] Injecting {len(queued)} queued message(s) "
                f"for thread_id={thread_id}"
            )

            # Emit SSE custom event so frontend knows the message was delivered
            try:
                writer = get_stream_writer()
                writer(
                    {
                        "type": "queued_message_injected",
                        "thread_id": thread_id,
                        "count": len(queued),
                        "messages": [
                            {
                                "content": q["content"],
                                "user_id": q.get("user_id"),
                                "timestamp": q.get("timestamp"),
                            }
                            for q in queued
                        ],
                        "timestamp": time.time(),
                    }
                )
            except Exception:
                # Stream writer may not be available in all contexts
                pass

            return {"messages": [human_msg]}

        except Exception as e:
            logger.error(f"[MessageQueue] Error checking queue: {e}")
            return None
