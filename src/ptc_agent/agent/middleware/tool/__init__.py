"""Tool-related middlewares for LangChain agents.

This module contains middleware classes that handle tool input/output processing:
- Argument parsing: Converts JSON-encoded string arguments to Python objects
- Error handling: Catches tool execution errors and returns simplified messages
- Result normalization: Ensures all tool results are strings for LLM compatibility
"""

from ptc_agent.agent.middleware.tool.argument_parsing import ToolArgumentParsingMiddleware
from ptc_agent.agent.middleware.tool.empty_call_retry import EmptyToolCallRetryMiddleware
from ptc_agent.agent.middleware.tool.error_handling import (
    ToolErrorHandlingMiddleware,
    simplify_tool_error,
)
from ptc_agent.agent.middleware.tool.result_normalization import ToolResultNormalizationMiddleware

__all__ = [
    "EmptyToolCallRetryMiddleware",
    "ToolArgumentParsingMiddleware",
    "ToolErrorHandlingMiddleware",
    "ToolResultNormalizationMiddleware",
    "simplify_tool_error",
]
