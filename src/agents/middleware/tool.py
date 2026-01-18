"""Tool-related middlewares for LangChain agents.

This module contains middleware classes that handle tool input/output processing:
- Argument parsing: Converts JSON-encoded string arguments to Python objects
- Error handling: Catches tool execution errors and returns simplified messages
- Result normalization: Ensures all tool results are strings for LLM compatibility
"""
import json
import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)


def simplify_tool_error(error: Exception) -> str:
    """Simplify tool error messages by removing verbose input args.

    Args:
        error: The exception raised during tool execution

    Returns:
        Simplified error message string (max 200 chars)

    Example:
        ValidationError with missing field -> "Field 'file_path': field required"
        Generic error -> "Error message..." (truncated if too long)
    """
    # Handle Pydantic ValidationError (missing/invalid fields)
    if hasattr(error, 'errors') and callable(error.errors):
        errors = error.errors()
        if errors:
            # Extract first error details
            first_error = errors[0]
            field = first_error.get('loc', ['unknown'])[-1]  # Get last part of location tuple
            msg = first_error.get('msg', 'validation failed')
            return f"Field '{field}': {msg}"

    # Generic error - truncate if too long
    error_str = str(error)
    if len(error_str) > 200:
        return error_str[:200] + "..."
    return error_str


class ToolArgumentParsingMiddleware(AgentMiddleware):
    """Middleware that parses JSON string arguments to proper Python types.

    This middleware handles cases where LLM providers return tool arguments as
    JSON-encoded strings instead of properly deserialized Python objects.
    It automatically parses string arguments to their proper types before
    tool execution, preventing Pydantic validation errors.

    Common issue: Some LLMs return `'["item1", "item2"]'` (string) instead of
    `["item1", "item2"]` (list), causing validation errors like:
    "Input should be a valid list [type=list_type, input_value='[...]', input_type=str]"
    """

    def _parse_args(self, args):
        """Parse args dict, converting JSON strings to proper types."""
        if not isinstance(args, dict):
            return args

        parsed_args = {}
        for key, value in args.items():
            if isinstance(value, str):
                # Try to parse as JSON if it looks like a JSON structure
                if (value.startswith('[') and value.endswith(']')) or \
                   (value.startswith('{') and value.endswith('}')):
                    try:
                        parsed_args[key] = json.loads(value)
                        logger.debug(f"Parsed JSON string argument '{key}': {value[:50]}... -> {type(parsed_args[key])}")
                    except json.JSONDecodeError:
                        # Not valid JSON, keep as string
                        parsed_args[key] = value
                else:
                    parsed_args[key] = value
            else:
                parsed_args[key] = value

        return parsed_args

    def wrap_tool_call(self, request, handler):
        """Synchronous tool argument parser."""
        # Parse arguments before passing to handler
        if "args" in request.tool_call:
            request.tool_call["args"] = self._parse_args(request.tool_call["args"])
        return handler(request)

    async def awrap_tool_call(self, request, handler):
        """Asynchronous tool argument parser."""
        # Parse arguments before passing to handler
        if "args" in request.tool_call:
            request.tool_call["args"] = self._parse_args(request.tool_call["args"])
        return await handler(request)


class ToolErrorHandlingMiddleware(AgentMiddleware):
    """Middleware that handles tool execution errors with simplified messages.

    This middleware catches exceptions during tool execution and returns
    simplified error messages to the agent instead of crashing the workflow.
    This allows agents to see errors and potentially adjust their approach.

    Error simplification:
    - Pydantic ValidationErrors: Shows only field name and error message
    - Generic errors: Truncated to 200 characters max
    - Removes verbose input arguments that make errors unreadable
    """

    def _format_error_message(self, error: Exception, tool_name: str = None) -> str:
        """Format error message with tool name prefix.

        Args:
            error: The exception that occurred
            tool_name: Name of the tool that failed (optional)

        Returns:
            Formatted error message string
        """
        # Simplify error message
        simplified = simplify_tool_error(error)

        # Add tool name prefix if available
        if tool_name:
            return f"Tool '{tool_name}' failed: {simplified}"
        return f"Tool execution failed: {simplified}"

    def wrap_tool_call(self, request, handler):
        """Synchronous tool error handler."""
        try:
            return handler(request)
        except Exception as e:
            tool_name = request.tool_call.get("name", "unknown")
            error_message = self._format_error_message(e, tool_name)
            return ToolMessage(
                content=error_message,
                tool_call_id=request.tool_call["id"],
                status="error"
            )

    async def awrap_tool_call(self, request, handler):
        """Asynchronous tool error handler."""
        try:
            return await handler(request)
        except Exception as e:
            tool_name = request.tool_call.get("name", "unknown")
            error_message = self._format_error_message(e, tool_name)
            return ToolMessage(
                content=error_message,
                tool_call_id=request.tool_call["id"],
                status="error"
            )


class ToolResultNormalizationMiddleware(AgentMiddleware):
    """Middleware that normalizes tool results to strings for LLM compatibility.

    This middleware ensures all tool results are returned as strings for LLM compatibility.
    Some tools may return Python objects (lists, dicts, None, etc.) that cause type errors
    when sent to LLM APIs that expect ToolMessage content to be a string.

    Common issue: OpenAI API returns BadRequestError when ToolMessage content is an array:
    "The parameter `input` specified in the request are not valid: `Mismatch type string with value array`"

    This middleware normalizes all tool results:
    - Strings: Pass through unchanged
    - Lists/Dicts: Convert to JSON string using json.dumps()
    - None: Convert to empty string ""
    - Other types: Convert to string using str()
    """

    def _normalize_result(self, result: Any) -> str:
        """Normalize tool result to a string.

        Args:
            result: The result from tool execution (any type)

        Returns:
            Normalized string representation
        """
        # Already a string - pass through
        if isinstance(result, str):
            return result

        # None - return empty JSON array
        if result is None:
            return json.dumps([])

        # Lists and dicts - convert to JSON string
        if isinstance(result, (list, dict)):
            try:
                return json.dumps(result, ensure_ascii=False)
            except (TypeError, ValueError) as e:
                logger.warning(f"Failed to JSON serialize tool result: {e}, falling back to str()")
                return str(result)

        # ToolMessage - normalize its content
        if isinstance(result, ToolMessage):
            normalized_content = self._normalize_result(result.content)
            return ToolMessage(
                content=normalized_content,
                tool_call_id=result.tool_call_id,
                status=result.status if hasattr(result, 'status') else None
            )

        # Other types - convert to string
        return str(result)

    def wrap_tool_call(self, request, handler):
        """Synchronous tool result normalizer."""
        result = handler(request)

        # Normalize ToolMessage content
        if isinstance(result, ToolMessage):
            result.content = self._normalize_result(result.content)

        return result

    async def awrap_tool_call(self, request, handler):
        """Asynchronous tool result normalizer."""
        result = await handler(request)

        # Normalize ToolMessage content
        if isinstance(result, ToolMessage):
            result.content = self._normalize_result(result.content)

        return result
