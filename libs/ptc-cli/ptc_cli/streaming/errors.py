"""API error detection and formatting for graceful error handling."""

import os
import re

import structlog

logger = structlog.get_logger(__name__)

# Cache for lazily-loaded API error types
_cache: dict[str, tuple[type[Exception], ...]] = {}


def _get_api_error_types() -> tuple[type[Exception], ...]:
    """Lazily load API error types from installed SDKs."""
    if "types" in _cache:
        return _cache["types"]

    error_types: list[type[Exception]] = []

    # Anthropic SDK errors
    try:
        from anthropic import APIConnectionError as AnthropicConnectionError
        from anthropic import APIError as AnthropicAPIError
        from anthropic import AuthenticationError as AnthropicAuthError
        from anthropic import RateLimitError as AnthropicRateLimitError

        error_types.extend(
            [
                AnthropicRateLimitError,
                AnthropicAuthError,
                AnthropicConnectionError,
                AnthropicAPIError,
            ]
        )
    except ImportError:
        pass

    # OpenAI SDK errors
    try:
        from openai import APIConnectionError as OpenAIConnectionError
        from openai import APIError as OpenAIAPIError
        from openai import AuthenticationError as OpenAIAuthError
        from openai import RateLimitError as OpenAIRateLimitError

        error_types.extend(
            [
                OpenAIRateLimitError,
                OpenAIAuthError,
                OpenAIConnectionError,
                OpenAIAPIError,
            ]
        )
    except ImportError:
        pass

    _cache["types"] = tuple(error_types) if error_types else ()
    return _cache["types"]


def is_api_error(e: Exception) -> bool:
    """Check if an exception is an API error (rate limit, auth, connection).

    Args:
        e: The exception to check.

    Returns:
        True if it's a recognized API error from Anthropic or OpenAI SDKs.
    """
    error_types = _get_api_error_types()
    if not error_types:
        return False
    return isinstance(e, error_types)


def get_api_error_message(e: Exception) -> str:
    """Format a clean, user-friendly error message for API errors.

    Args:
        e: The API exception.

    Returns:
        Formatted error message with Rich markup.
    """
    # Log the full error for debugging
    logger.error("API error occurred", error=str(e), error_type=type(e).__name__)

    error_str = str(e)
    error_type = type(e).__name__

    # Determine error category and format message
    if "RateLimitError" in error_type:
        title = "Rate limit exceeded"
    elif "AuthenticationError" in error_type:
        title = "Authentication failed"
    elif "ConnectionError" in error_type:
        title = "Connection failed"
    else:
        title = "API error"

    # Extract the actual error message (often in JSON format)
    message = _extract_error_message(error_str)

    lines = [
        f"[red]{title}[/red]",
        f"  {message}",
        "",
        f"[dim]Check {os.environ.get('PTC_CLI_LOG_FILE', '~/.ptc-agent/logs')} for full details.[/dim]",
    ]

    return "\n".join(lines)


def _extract_error_message(error_str: str) -> str:
    """Extract the human-readable message from an API error string.

    Args:
        error_str: The full error string, often containing JSON.

    Returns:
        A cleaner, more readable error message.
    """
    # Many API errors have format: "Error code: XXX - {'type': ..., 'error': {'message': '...'}}"
    # Try to extract just the message part
    if "'message':" in error_str:
        match = re.search(r"'message':\s*'([^']+)'", error_str)
        if match:
            return match.group(1)

    # Truncate long error strings
    max_len = 200
    if len(error_str) > max_len:
        return error_str[:max_len] + "..."

    return error_str
