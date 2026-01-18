"""
State restoration module for multi-round conversation support.

This module provides functions to restore workflow state from previous threads,
enabling follow-up conversations that maintain context including:
- Observations and research findings
- Resources and citations
- Tool results and execution history
- Market type and configuration settings
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import uuid4

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)

from src.server.database import conversation_db
from src.server.models.chat import ChatRequest

logger = logging.getLogger(__name__)


def deserialize_messages(serialized_messages: List[Dict[str, Any]]) -> List[BaseMessage]:
    """
    Convert serialized messages back to LangChain message objects.

    Reverses the serialization done by serialize_message() in workflow_request.py.

    Args:
        serialized_messages: List of message dictionaries from database

    Returns:
        List of LangChain BaseMessage objects

    Example:
        >>> messages = deserialize_messages([
        ...     {"role": "human", "content": "Hello"},
        ...     {"role": "ai", "content": "Hi there!"}
        ... ])
    """
    if not serialized_messages:
        return []

    result = []

    for msg in serialized_messages:
        if not isinstance(msg, dict):
            logger.warning(f"Skipping non-dict message: {msg}")
            continue

        role = msg.get("role", msg.get("type", "human"))
        content = msg.get("content", "")

        # Map role to LangChain message type
        if role in ["human", "user"]:
            message = HumanMessage(content=content)
        elif role in ["ai", "assistant"]:
            message = AIMessage(
                content=content,
                tool_calls=msg.get("tool_calls", []),
                additional_kwargs=msg.get("additional_kwargs", {})
            )
        elif role == "tool":
            message = ToolMessage(
                content=content,
                tool_call_id=msg.get("tool_call_id", "")
            )
        elif role == "system":
            message = SystemMessage(content=content)
        else:
            # Unknown role, default to HumanMessage
            logger.warning(f"Unknown message role: {role}, defaulting to HumanMessage")
            message = HumanMessage(content=content)

        # Restore ID if present
        if "id" in msg:
            message.id = msg["id"]

        result.append(message)

    return result


async def restore_state_from_checkpoint(
    graph,
    last_thread_id: str
) -> Optional[Dict[str, Any]]:
    """
    Restore state from LangGraph checkpoint store.

    This is the preferred method as it retrieves the most recent state
    directly from LangGraph's internal checkpoint mechanism.

    Args:
        graph: LangGraph compiled graph with checkpoint store
        last_thread_id: Thread ID to restore state from

    Returns:
        State dictionary or None if not found
    """
    try:
        # Create config for the last thread
        config = {
            "configurable": {
                "thread_id": last_thread_id
            }
        }

        # Get the latest state snapshot from LangGraph
        state_snapshot = await graph.aget_state(config)

        if not state_snapshot or not state_snapshot.values:
            logger.warning(f"No checkpoint state found for thread {last_thread_id}")
            return None

        logger.debug(f"Successfully restored state from checkpoint for thread {last_thread_id}")
        return dict(state_snapshot.values)

    except Exception as e:
        logger.debug(f"Failed to restore from checkpoint for thread {last_thread_id}: {e}")
        return None


async def restore_state_from_database(
    last_thread_id: str,
    pair_index: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Restore state from database state_snapshot.

    Fallback method when checkpoint store is unavailable or out of sync.

    Args:
        last_thread_id: Thread ID to restore state from
        pair_index: Specific pair index (None = latest)

    Returns:
        State dictionary or None if not found
    """
    try:
        # Get all responses for the thread
        responses = await conversation_db.get_responses_for_thread(last_thread_id)

        if not responses:
            logger.warning(f"No responses found in database for thread {last_thread_id}")
            return None

        # Find the target response
        if pair_index is not None:
            target_response = next(
                (r for r in responses if r.get("pair_index") == pair_index),
                None
            )
        else:
            # Get the latest response
            target_response = max(responses, key=lambda r: r.get("pair_index", 0))

        if not target_response:
            logger.warning(f"No matching response found for thread {last_thread_id}")
            return None

        # Extract state_snapshot
        state_snapshot = target_response.get("state_snapshot")

        if not state_snapshot or not isinstance(state_snapshot, dict):
            logger.warning(f"Invalid state_snapshot in response for thread {last_thread_id}")
            return None

        logger.debug(f"Successfully restored state from database for thread {last_thread_id}")
        return state_snapshot

    except Exception as e:
        logger.debug(f"Failed to restore from database for thread {last_thread_id}: {e}")
        return None


async def recover_from_messages(last_thread_id: str) -> Optional[Dict[str, Any]]:
    """
    Attempt to reconstruct minimal state from query-response messages.

    Last resort recovery method when neither checkpoint nor state_snapshot is available.
    Creates a minimal state with just the message history.

    Args:
        last_thread_id: Thread ID to recover messages from

    Returns:
        Minimal state dictionary with messages or None
    """
    try:
        # Get all query-response pairs for the thread
        pairs = await conversation_db.get_query_response_pairs(last_thread_id)

        if not pairs:
            logger.warning(f"No query-response pairs found for thread {last_thread_id}")
            return None

        # Reconstruct message history from pairs
        messages = []

        for pair in pairs:
            query = pair.get("query", {})
            response = pair.get("response", {})

            # Add user message with preserved ID
            if query.get("content"):
                messages.append({
                    "role": "human",
                    "content": query["content"],
                    "id": query.get("query_id"),  # Preserve original query ID
                })

            # Add AI response with preserved ID
            final_output = response.get("final_output", {})
            if final_output.get("text"):
                messages.append({
                    "role": "ai",
                    "content": final_output["text"],
                    "id": response.get("response_id"),  # Preserve original response ID
                })

        if not messages:
            logger.warning(f"No messages could be reconstructed for thread {last_thread_id}")
            return None

        # Create minimal state with just messages
        minimal_state = {
            "messages": deserialize_messages(messages)
        }

        logger.debug(f"Recovered minimal state with {len(messages)} messages for thread {last_thread_id}")
        return minimal_state

    except Exception as e:
        logger.error(f"Failed to recover from messages for thread {last_thread_id}: {e}")
        return None


async def restore_state_with_fallback(
    graph,
    last_thread_id: str
) -> Optional[Dict[str, Any]]:
    """
    Restore state with automatic fallback chain.

    Tries methods in order of preference:
    1. LangGraph checkpoint (most up-to-date)
    2. Database state_snapshot (reliable fallback)
    3. Message-based recovery (last resort)

    Args:
        graph: LangGraph compiled graph
        last_thread_id: Thread ID to restore from

    Returns:
        Restored state dictionary or None if all methods fail
    """
    # Try checkpoint first (preferred method)
    state = await restore_state_from_checkpoint(graph, last_thread_id)
    if state:
        logger.debug(f"✓ Restored state from checkpoint for thread {last_thread_id}")
        return state

    # Fallback to database
    state = await restore_state_from_database(last_thread_id)
    if state:
        logger.debug(f"✓ Restored state from database for thread {last_thread_id}")
        return state

    # Last resort: message recovery
    state = await recover_from_messages(last_thread_id)
    if state:
        logger.warning(f"⚠ Recovered minimal state from messages for thread {last_thread_id}")
        return state

    logger.error(f"✗ Failed to restore state for thread {last_thread_id} - all methods exhausted")
    return None


def merge_states(
    restored_state: Dict[str, Any],
    request: ChatRequest
) -> Dict[str, Any]:
    """
    Merge restored state with new request parameters using selective preservation.

    Preservation strategy:
    - PRESERVE: observations, resources, used_tool_results, market_type, files
    - RESET: current_plan, plan_iterations, pending_file_events, retry_counts
    - OVERRIDE: deepthinking, auto_accepted_plan, prompt_language, locale, agent_llm_preset
    - APPEND: messages (add new messages to existing)

    Args:
        restored_state: State restored from previous thread
        request: New ChatRequest with updated parameters

    Returns:
        Merged state dictionary ready for graph execution
    """
    # Start with a copy of restored state
    merged_state = dict(restored_state)

    # === PRESERVE: Keep valuable accumulated context ===
    # These fields contain research findings and should persist
    preserved_fields = [
        "observations",      # Research findings from agents
        "resources",        # RAG resources and citations
        "used_tool_results", # Tool execution history
        "market_type",      # Identified market type (A股/美股/港股)
    ]

    # Only preserve files if they exist and are relevant
    # (could be made configurable in the future)
    if "files" in restored_state and restored_state["files"]:
        preserved_fields.append("files")

    # === RESET: Clear workflow-specific state ===
    # These fields should start fresh for each new query
    reset_fields = {
        "current_plan": None,
        "plan_iterations": 0,
        "pending_file_events": [],
        "file_operations_log": [],  # Reset file operations audit trail for new query
        "retry_counts": {
            "planner": 3,
            "coder": 3,
            "data_agent": 3,
            "reporter": 3,
        },
        "final_report": "",  # Clear previous report
        "deepthinking_results": None,
    }

    for field, default_value in reset_fields.items():
        merged_state[field] = default_value

    # === OVERRIDE: Apply new configuration from request ===
    # These are user preferences that may change between rounds
    if request.deepthinking is not None:
        merged_state["deepthinking"] = request.deepthinking

    if request.auto_accepted_plan is not None:
        merged_state["auto_accepted_plan"] = request.auto_accepted_plan

    if request.prompt_language:
        merged_state["prompt_language"] = request.prompt_language

    if request.locale:
        merged_state["locale"] = request.locale

    if request.agent_llm_preset:
        merged_state["agent_llm_preset"] = request.agent_llm_preset

    if request.msg_type:
        merged_state["msg_type"] = request.msg_type

    if request.stock_code:
        merged_state["stock_code"] = request.stock_code

    # === APPEND: Add new messages to conversation history ===
    existing_messages = merged_state.get("messages", [])

    # Convert existing messages to LangChain format if needed
    if existing_messages and isinstance(existing_messages[0], dict):
        existing_messages = deserialize_messages(existing_messages)

    # Add new messages from request
    new_messages = []
    for msg in request.messages:
        role = msg.role
        content = msg.content

        if isinstance(content, list):
            # Handle multimodal content (text + images)
            content_str = " ".join(
                item.text for item in content if hasattr(item, "text") and item.text
            )
        else:
            content_str = str(content)

        if role in ["user", "human"]:
            new_messages.append(HumanMessage(content=content_str))
        elif role in ["assistant", "ai"]:
            new_messages.append(AIMessage(content=content_str))

    merged_state["messages"] = existing_messages + new_messages

    # === Store additional_context_raw for later processing ===
    if request.additional_context:
        merged_state["additional_context_raw"] = [
            ctx.model_dump() if hasattr(ctx, "model_dump") else ctx
            for ctx in request.additional_context
        ]

    logger.debug(
        f"Merged state: preserved {len(preserved_fields)} fields, "
        f"reset {len(reset_fields)} fields, "
        f"added {len(new_messages)} new messages"
    )

    return merged_state


async def restore_files_from_database(conversation_id: str) -> Dict[str, Any]:
    """
    Restore files from database for follow-up conversations.

    Converts database string content back to FileData format (list[str])
    for proper state reconstruction. This enables bidirectional conversion
    between database storage (string) and state format (list of lines).

    Args:
        conversation_id: Conversation ID to restore files from

    Returns:
        Dict mapping file_path to FileData objects with content as list[str]

    Example:
        >>> files = await restore_files_from_database("conv-123")
        >>> files["/report.md"]["content"]
        ['# Report', 'Line 2', 'Line 3']  # list[str], ready for state
    """
    from src.tools.core.filesystem.utils import string_to_file_data

    try:
        # Get files from database (content is string)
        db_files = await conversation_db.get_files_for_conversation(conversation_id)

        # Convert database strings to FileData format
        restored_files = {}
        for file_path, file_info in db_files.items():
            content_string = file_info.get('content')
            if not content_string:
                logger.debug(f"Skipping file with no content: {file_path}")
                continue

            # Convert string → FileData (list[str]) using helper
            file_data = string_to_file_data(
                content=content_string,
                created_at=file_info.get('created_at'),
                modified_at=file_info.get('updated_at')  # DB uses 'updated_at', FileData uses 'modified_at'
            )

            restored_files[file_path] = file_data

        logger.info(
            f"Restored {len(restored_files)} files from database "
            f"for conversation {conversation_id}"
        )
        return restored_files

    except Exception as e:
        logger.error(f"Failed to restore files from database: {e}", exc_info=True)
        # Return empty dict on error - files not critical for workflow start
        return {}


def parse_last_thread_id(additional_context: Optional[List[Any]]) -> Optional[str]:
    """
    Extract last_thread ID from additional_context.

    Looks for context items with type="last_thread" and extracts the ID.

    Args:
        additional_context: List of context items from ChatRequest

    Returns:
        Thread ID string or None if not found

    Example:
        >>> parse_last_thread_id([
        ...     {"type": "last_thread", "id": "abc-123"}
        ... ])
        'abc-123'
    """
    if not additional_context:
        return None

    for ctx in additional_context:
        # Handle both dict and Pydantic model
        if isinstance(ctx, dict):
            ctx_type = ctx.get("type")
            ctx_id = ctx.get("id")
        elif hasattr(ctx, "type") and hasattr(ctx, "id"):
            ctx_type = ctx.type
            ctx_id = ctx.id
        else:
            continue

        if ctx_type == "last_thread" and ctx_id:
            logger.info(f"Found last_thread context with ID: {ctx_id}")
            return ctx_id

    return None
