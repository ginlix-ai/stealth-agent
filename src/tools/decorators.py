
import logging
import functools
from typing import Any, Callable, Type, TypeVar, Dict, Optional
from contextvars import ContextVar
from collections import defaultdict

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ========== Tool Usage Tracking ==========

class ToolUsageTracker:
    """
    Track tool usage counts for infrastructure cost calculation.

    This class is used to record how many times each tool is called
    during workflow execution, which is then used to calculate
    infrastructure credits (e.g., Tavily searches, analysis tools).
    """

    def __init__(self, thread_id: Optional[str] = None):
        """
        Initialize usage tracker with empty counts.

        Args:
            thread_id: Optional workflow thread identifier for tracker lookup
        """
        self.usage: Dict[str, int] = defaultdict(int)
        self.thread_id = thread_id

    def record_usage(self, tool_name: str, count: int = 1) -> None:
        """
        Record tool usage.

        Args:
            tool_name: Tool class name (e.g., "TavilySearchTool")
            count: Number of uses (default: 1)
        """
        if count > 0:
            self.usage[tool_name] += count
            logger.debug(f"[ToolUsageTracker] Recorded {tool_name} x{count}")

    def get_summary(self) -> Dict[str, int]:
        """
        Get usage summary as a regular dict.

        Returns:
            Dict mapping tool names to usage counts
        """
        return dict(self.usage)

    def reset(self) -> None:
        """Reset all usage counts."""
        self.usage.clear()

    def __repr__(self) -> str:
        total_calls = sum(self.usage.values())
        return f"ToolUsageTracker(tools={len(self.usage)}, total_calls={total_calls})"


# ContextVar storage for tool usage tracker
# This follows the same pattern as ExecutionTracker (agent message tracking)
_tool_usage_context: ContextVar[Optional[ToolUsageTracker]] = ContextVar(
    'tool_usage_context',
    default=None
)


def start_tool_tracking() -> ToolUsageTracker:
    """
    Start tracking tool usage for the current context.

    Returns:
        ToolUsageTracker instance

    Usage:
        tracker = start_tool_tracking()
        # ... tools are called ...
        usage_summary = tracker.get_summary()
    """
    tracker = ToolUsageTracker()
    _tool_usage_context.set(tracker)
    logger.debug("[ToolUsageTracker] Started tracking")
    return tracker


def get_tool_tracker() -> Optional[ToolUsageTracker]:
    """
    Get the current tool usage tracker from ContextVar.

    Returns:
        ToolUsageTracker instance or None if not tracking
    """
    tracker = _tool_usage_context.get()
    if tracker:
        logger.debug("[ToolUsageTracker] Found tracker via ContextVar")
    return tracker


def stop_tool_tracking() -> Optional[Dict[str, int]]:
    """
    Stop tracking and return usage summary.

    Clears the ContextVar tracker.

    Returns:
        Usage summary dict or None if not tracking
    """
    tracker = _tool_usage_context.get()

    if tracker:
        summary = tracker.get_summary()
        # Clear ContextVar
        _tool_usage_context.set(None)

        return summary

    logger.warning("[ToolUsageTracker] stop_tool_tracking() called but no tracker found")
    return None


def log_io(func: Callable) -> Callable:
    """
    A decorator that logs the input parameters and output of a tool function.

    Args:
        func: The tool function to be decorated

    Returns:
        The wrapped function with input/output logging
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Log input parameters
        func_name = func.__name__
        params = ", ".join(
            [*(str(arg) for arg in args), *(f"{k}={v}" for k, v in kwargs.items())]
        )
        logger.debug(f"开始工具调用 {func_name} 参数: {params}")

        # Execute the function
        result = func(*args, **kwargs)

        # Log the output
        logger.debug(f"工具调用结束 {func_name} 结果: {result}")

        return result

    return wrapper


class LoggedToolMixin:
    """A mixin class that adds logging and usage tracking to any tool."""

    def _log_operation(self, method_name: str, *args: Any, **kwargs: Any) -> None:
        """Helper method to log tool operations."""
        tool_name = self.__class__.__name__.replace("Logged", "")
        params = ", ".join(
            [*(str(arg) for arg in args), *(f"{k}={v}" for k, v in kwargs.items())]
        )
        logger.debug(f"开始工具调用 {tool_name}.{method_name} 参数: {params}")

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Override _run method to add logging and usage tracking."""
        # Get base tool name (without "Logged" prefix)
        tool_name = self.__class__.__name__.replace("Logged", "")

        # Log operation start
        self._log_operation("_run", *args, **kwargs)

        # Track tool usage (if tracker is active)
        tracker = get_tool_tracker()
        if tracker:
            tracker.record_usage(tool_name, count=1)
        else:
            logger.debug(f"[ToolUsageTracker] No tracker available, skipping usage recording for tool={tool_name}")

        # Execute the tool
        result = super()._run(*args, **kwargs)

        # Log operation end
        logger.debug(
            f"工具调用结束 {tool_name} 结果: {result}"
        )

        return result

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        """Override _arun method to add logging and usage tracking (async version)."""
        # Get base tool name (without "Logged" prefix)
        tool_name = self.__class__.__name__.replace("Logged", "")

        # Log operation start
        self._log_operation("_arun", *args, **kwargs)

        # Track tool usage (if tracker is active)
        tracker = get_tool_tracker()
        if tracker:
            tracker.record_usage(tool_name, count=1)
        else:
            logger.debug(f"[ToolUsageTracker] No tracker available, skipping usage recording for tool={tool_name}")

        # Execute the tool (async)
        result = await super()._arun(*args, **kwargs)

        # Log operation end
        logger.debug(
            f"工具调用结束 {tool_name} 结果: {result}"
        )

        return result

def create_logged_tool(base_tool_class: Type[T]) -> Type[T]:
    """
    Factory function to create a logged version of any tool class.

    Args:
        base_tool_class: The original tool class to be enhanced with logging

    Returns:
        A new class that inherits from both LoggedToolMixin and the base tool class
    """

    class LoggedTool(LoggedToolMixin, base_tool_class):
        pass

    # Set a more descriptive name for the class
    LoggedTool.__name__ = f"Logged{base_tool_class.__name__}"
    return LoggedTool
