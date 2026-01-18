"""
Message tracking helper functions.

Provides convenient functions for tracking messages in common patterns:
- Agent messages with automatic tool call extraction
- Subgraph worker messages
- Single message tracking with reasoning preservation
"""

import logging
from typing import Any, Dict, List, Optional

from .core import ExecutionTracker, ToolCallProcessor

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions for Common Tracking Patterns
# ============================================================================

def track_agent_messages_with_tools(
    agent_name: str,
    messages: List[Any],
    extract_tool_calls: bool = True
) -> None:
    """Track agent messages with automatic tool call extraction and error handling.

    Args:
        agent_name: Full agent name/path (e.g., 'deep_research/data_agent')
        messages: List of messages to track
        extract_tool_calls: Whether to extract and track tool calls
    """
    try:
        if not messages:
            return

        # Update tracker with agent-scoped messages
        ExecutionTracker.update_context(
            agent_name=agent_name,
            messages=messages
        )

        # Extract and track tool calls if requested
        if extract_tool_calls:
            processor = ToolCallProcessor()
            tool_calls = processor.extract_tool_calls(messages)
            if tool_calls:
                ExecutionTracker.update_context(tool_calls=tool_calls)
                logger.debug(f"[Tracking] {agent_name} executed {len(tool_calls)} tool calls")
    except Exception as e:
        # Don't break execution if tracking fails
        logger.warning(f"[Tracking] Failed to track {agent_name}: {e}")


def track_subgraph_worker_messages(
    agent_name: str,
    result: Dict[str, Any],
    message_key: str = "worker_messages"
) -> None:
    """Track messages from subgraph results with error handling.

    Args:
        agent_name: Agent name for organizing messages
        result: Subgraph result dictionary
        message_key: Key to extract messages from result
    """
    try:
        worker_messages = result.get(message_key, [])
        if worker_messages:
            ExecutionTracker.update_context(
                agent_name=agent_name,
                messages=worker_messages
            )
            logger.debug(f"[Tracking] {agent_name} subgraph produced {len(worker_messages)} messages")
    except Exception as e:
        logger.warning(f"[Tracking] Failed to track {agent_name} subgraph: {e}")


def track_single_message(
    agent_name: str,
    content: Optional[str] = None,
    message: Optional[Any] = None,
    message_type: str = "AIMessage",
    name: Optional[str] = None
) -> None:
    """Track a single message with error handling.

    Args:
        agent_name: Agent name for organizing messages
        content: Message content string (for creating new message, deprecated - use message instead)
        message: Full message object to track (preserves reasoning and metadata)
        message_type: Type of message (AIMessage, HumanMessage, etc.) - only used when content is provided
        name: Optional message name field - only used when content is provided
    """
    try:
        from langchain_core.messages import AIMessage, HumanMessage

        # Prefer tracking the full message object if provided
        if message is not None:
            # Track the provided message directly (preserves reasoning)
            ExecutionTracker.update_context(
                agent_name=agent_name,
                messages=[message]
            )
            logger.debug(f"[Tracking] {agent_name} full message tracked")
        elif content is not None:
            # Backward compatibility: Create message from content string
            if message_type == "AIMessage":
                new_message = AIMessage(content=content, name=name or agent_name)
            elif message_type == "HumanMessage":
                new_message = HumanMessage(content=content, name=name or agent_name)
            else:
                logger.warning(f"[Tracking] Unknown message type: {message_type}, using AIMessage")
                new_message = AIMessage(content=content, name=name or agent_name)

            ExecutionTracker.update_context(
                agent_name=agent_name,
                messages=[new_message]
            )
            logger.debug(f"[Tracking] {agent_name} message tracked from content string")
        else:
            logger.warning(f"[Tracking] {agent_name}: Neither message nor content provided")

    except Exception as e:
        logger.warning(f"[Tracking] Failed to track {agent_name}: {e}")


# Public API
__all__ = [
    'track_agent_messages_with_tools',
    'track_subgraph_worker_messages',
    'track_single_message',
]
