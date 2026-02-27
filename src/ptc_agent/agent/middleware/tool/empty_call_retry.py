"""Retry middleware for empty tool_calls with tool_use stop_reason.

Some LLM providers (e.g. dashscope-anthropic with qwen models) may return
stop_reason="tool_use" but with an empty tool_calls list — the model intended
to call tools but the content was malformed/truncated and the SDK silently
dropped it.  LangGraph sees empty tool_calls and routes to __END__, stopping
the agent mid-task.

This middleware detects that mismatch and retries the model call.
"""

import logging

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)

# stop_reason values that indicate the model intended to call tools
_TOOL_USE_STOP_REASONS = {"tool_use", "tool_calls"}


class EmptyToolCallRetryMiddleware(AgentMiddleware):
    """Retries when stop_reason indicates tool_use but tool_calls is empty."""

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def _should_retry(self, ai_msg: AIMessage) -> bool:
        meta = getattr(ai_msg, "response_metadata", {}) or {}
        stop = meta.get("stop_reason") or meta.get("finish_reason") or ""
        return (
            stop in _TOOL_USE_STOP_REASONS
            and not getattr(ai_msg, "tool_calls", None)
            and not getattr(ai_msg, "invalid_tool_calls", None)
        )

    def _log_retry(self, ai_msg: AIMessage, attempt: int) -> None:
        meta = getattr(ai_msg, "response_metadata", {}) or {}
        stop = meta.get("stop_reason") or meta.get("finish_reason")
        logger.warning(
            "[EmptyToolCallRetry] stop_reason=%s but tool_calls is empty, "
            "retrying (%d/%d)",
            stop,
            attempt + 1,
            self.max_retries,
        )

    def wrap_model_call(self, request, handler):
        for attempt in range(1 + self.max_retries):
            response = handler(request)
            ai_msg = response.result[0]
            if not self._should_retry(ai_msg):
                return response
            self._log_retry(ai_msg, attempt)
        return response  # return last response even if still broken

    async def awrap_model_call(self, request, handler):
        for attempt in range(1 + self.max_retries):
            response = await handler(request)
            ai_msg = response.result[0]
            if not self._should_retry(ai_msg):
                return response
            self._log_retry(ai_msg, attempt)
        return response
