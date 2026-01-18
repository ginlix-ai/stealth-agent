"""
Content Normalization for SSE Streaming

This module provides SSE-specific content normalization for streaming responses.
It wraps the core extraction utilities from src.llms.content_utils and adds
SSE-specific features like thinking status signal detection.

SSE-specific features:
- Thinking/reasoning status signal detection (in_progress, completed indicators)
- Stream-appropriate content filtering

Core extraction logic is provided by src.llms.content_utils.extract_content_with_type
"""

from typing import Any, Optional, Tuple, Dict
import logging
from src.llms.content_utils import extract_content_with_type

logger = logging.getLogger(__name__)


def normalize_text_content(content: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Normalize content to extract plain text or reasoning (SSE streaming version).

    This is an SSE-specific wrapper around extract_content_with_type that adds
    status signal detection for streaming scenarios.

    Args:
        content: Raw content from LLM (can be string, dict, list, etc.)

    Returns:
        Tuple of (text_content, content_type):
        - text_content: Plain text string if content is text-like or reasoning
        - content_type: "text", "reasoning", or None

    Examples:
        >>> normalize_text_content("Hello")
        ("Hello", "text")

        >>> normalize_text_content({"type": "thinking", "thinking": "analysis"})
        ("analysis", "reasoning")

        >>> normalize_text_content({"type": "reasoning", "summary": [{"text": "thought"}]})
        ("thought", "reasoning")

        >>> normalize_text_content({"summary": [{"type": "summary_text", "text": "thought"}]})
        ("thought", "reasoning")

        >>> normalize_text_content({"result": "data"})
        (None, None)
    """
    if content is None:
        return None, None

    # SSE-specific: Check for thinking status signals first
    # Status signals should not be treated as content
    if is_thinking_status_signal(content):
        return None, None

    # Delegate to core extraction utility
    return extract_content_with_type(content)


def normalize_reasoning_content(reasoning_content: Any) -> Optional[str]:
    """
    Normalize reasoning/thinking content to plain text.

    This specifically handles reasoning and thinking objects from different
    LLM providers, extracting only the text content.

    Args:
        reasoning_content: Raw reasoning content from LLM

    Returns:
        Plain text string or None if empty

    Examples:
        >>> normalize_reasoning_content({"type": "reasoning", "summary": [{"text": "analysis"}]})
        "analysis"

        >>> normalize_reasoning_content({"summary": [{"type": "summary_text", "text": "analysis"}]})
        "analysis"

        >>> normalize_reasoning_content([{"type": "thinking", "thinking": "thought"}])
        "thought"
    """
    if reasoning_content is None:
        return None

    # Use text normalization but only return text (ignore content_type)
    text, _ = normalize_text_content(reasoning_content)
    return text


def is_thinking_status_signal(content: Any) -> Optional[dict]:
    """
    Detect thinking/reasoning status signals (not actual content).

    These are status indicators from LLM providers that signal the model
    is actively reasoning/thinking, but contain no content yet.

    Args:
        content: Content to check for status signals

    Returns:
        Dict with status info if it's a signal, None otherwise:
        {
            "thinking_type": "reasoning" | "thinking",
            "status": "active" | "in_progress" | "completed",
            "index": int,
            "id": str (optional),
            "signature": str (optional)
        }

    Examples:
        >>> is_thinking_status_signal({"type": "reasoning", "status": "in_progress", "id": "rs_123"})
        {"thinking_type": "reasoning", "status": "in_progress", "index": 0, "id": "rs_123"}

        >>> is_thinking_status_signal({"type": "thinking", "signature": "abc", "index": 0})
        {"thinking_type": "thinking", "status": "active", "index": 0, "signature": "abc"}

        >>> is_thinking_status_signal({"type": "reasoning", "summary": [{"text": "content"}]})
        None  # Has content, not a status signal
    """
    # Handle single dict
    if isinstance(content, dict):
        return _check_single_status_signal(content)

    # Handle list with single item (common format)
    if isinstance(content, list) and len(content) == 1:
        return _check_single_status_signal(content[0])

    return None


# ============================================================================
# Helper Functions
# ============================================================================

def _check_single_status_signal(obj: Any) -> Optional[Dict]:
    """Check if a single object is a thinking status signal."""
    if not isinstance(obj, dict):
        return None

    obj_type = obj.get("type")

    # Reasoning status: type="reasoning" WITHOUT summary field
    if obj_type == "reasoning":
        # If it has summary, it's content not status
        if "summary" in obj:
            return None

        # If it has status field, it's a status signal
        # Response API sends status="in_progress" for reasoning start
        # Status can be: "in_progress", "completed", or other provider-specific values
        if "status" in obj:
            return {
                "thinking_type": "reasoning",
                "status": obj.get("status", "active"),
                "index": obj.get("index", 0),
                "id": obj.get("id"),
            }

    # Thinking status: type="thinking" WITHOUT thinking field
    if obj_type == "thinking":
        # If it has thinking field, it's content not status
        if "thinking" in obj:
            return None

        # If it has signature, it's a completion signal (Anthropic end-of-thinking)
        if "signature" in obj:
            return {
                "thinking_type": "thinking",
                "status": "completed",
                "index": obj.get("index", 0),
                "signature": obj.get("signature"),
            }

    return None


def extract_text_from_message_content(content: Any) -> str:
    """
    Helper function to extract plain text from message content.

    Handles Union[str, List[ContentItem]] format from ChatMessage.content.
    This is commonly used when extracting user input from request messages.

    Args:
        content: Message content (can be string or list of content items)

    Returns:
        Plain text extracted from content

    Examples:
        >>> extract_text_from_message_content("Hello world")
        "Hello world"

        >>> extract_text_from_message_content([{"type": "text", "text": "Hello"}, {"type": "text", "text": "world"}])
        "Hello world"

        >>> extract_text_from_message_content([])
        ""
    """
    if not content:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        # Extract text from list of content items
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif isinstance(item, str):
                text_parts.append(item)
        return " ".join(text_parts)

    # Fallback: convert to string
    return str(content)
