"""
Serialization helpers for agent messages.

Provides shared serialization logic to ensure consistent formatting and ordering
across API responses, database storage, and log files.
"""

from typing import Dict, List, Any, Optional
from src.utils.tracking.core import serialize_agent_message, renumber_agent_index


def serialize_agent_messages(
    agent_messages: Dict[str, List],
    agent_execution_index: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    """
    Serialize agent messages to JSON-safe format with metadata and proper ordering.

    Transforms LangChain message objects into dictionaries with:
    - message_index: Sequential index within each agent (0, 1, 2...)
    - agent_index: Relative execution index of agents (0, 1, 2...)

    Returns dict sorted by agent_index for consistent iteration order.

    Args:
        agent_messages: Raw agent messages (agent_name → list of LangChain messages)
        agent_execution_index: Absolute agent execution index (agent_name → index)

    Returns:
        Dict mapping agent names to agent entries with metadata, sorted by agent_index

    Example:
        >>> messages = {
        ...     "planner": [msg1, msg2],
        ...     "researcher/worker_0": [msg3, msg4]
        ... }
        >>> index = {"planner": 0, "researcher/worker_0": 2}
        >>> result = serialize_agent_messages(messages, index)
        >>> list(result.keys())
        ['planner', 'researcher/worker_0']  # Sorted by agent_index
        >>> result['planner']['agent_index']
        0
    """

    # Renumber agent_index to be relative (0, 1, 2...)
    relative_agent_index = renumber_agent_index(agent_execution_index or {})

    result = {}
    for agent_name, messages in agent_messages.items():
        # Serialize messages with message_index
        serialized_messages = [
            {**serialize_agent_message(msg), "message_index": idx}
            for idx, msg in enumerate(messages)
        ]

        # Build agent entry with agent_index only
        agent_entry = {
            "agent_index": relative_agent_index.get(agent_name, 999),
            "messages": serialized_messages
        }

        result[agent_name] = agent_entry

    # Sort by agent_index to ensure consistent iteration order
    sorted_result = dict(sorted(
        result.items(),
        key=lambda x: x[1].get("agent_index", 999)
    ))

    return sorted_result
