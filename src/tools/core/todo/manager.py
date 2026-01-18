"""Todo manager utilities for agent task tracking.

Provides checkout/checkin operations and helper functions for managing agent todos.
All functions are stateless - they don't modify state directly, but return updates.
"""

import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from .types import TodoItem, TodoStatus, validate_todo_list_dict

logger = logging.getLogger(__name__)


def checkout_todos(state: Dict[str, Any], agent_name: str) -> List[Dict[str, Any]]:
    """Checkout (retrieve) todos for a specific agent from state.

    This function retrieves the current todo list for an agent from the workflow state.
    If no todos exist for the agent, returns an empty list.

    Args:
        state: The workflow state containing agent_todos
        agent_name: Name of the agent (e.g., "data_agent", "researcher")

    Returns:
        List of todo dictionaries for the agent, or empty list if none exist
    """
    agent_todos = state.get("agent_todos", {})
    todos = agent_todos.get(agent_name, [])

    logger.info(f"[{agent_name}] Checked out {len(todos)} todos from state")
    if todos:
        for i, todo in enumerate(todos):
            logger.debug(f"  [{i}] {todo.get('status', 'unknown')}: {todo.get('content', 'No content')}")

    return todos


def checkin_todos(agent_name: str, todos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Checkin (save) todos for a specific agent back to state.

    This function prepares a state update dictionary to save the agent's todos.
    It does NOT modify state directly - it returns the update dict.

    Args:
        agent_name: Name of the agent (e.g., "data_agent", "researcher")
        todos: List of todo dictionaries to save

    Returns:
        Dictionary containing the state update to apply
    """
    # Validate todos before checkin
    is_valid, errors = validate_todo_list_dict(todos)
    if not is_valid:
        logger.warning(f"[{agent_name}] Todo validation warnings: {'; '.join(errors)}")

    logger.info(f"[{agent_name}] Checking in {len(todos)} todos to state")
    if todos:
        status_counts = {"pending": 0, "in_progress": 0, "completed": 0}
        for todo in todos:
            status = todo.get("status", "unknown")
            if status in status_counts:
                status_counts[status] += 1
        logger.debug(f"  Status summary: {status_counts}")

    # Return state update - this will be merged with existing agent_todos
    # The caller should handle merging this into the full state
    return {
        agent_name: todos
    }


def mark_in_progress(todos: List[Dict[str, Any]], index: int) -> List[Dict[str, Any]]:
    """Mark a specific todo as in_progress, ensuring only one is in_progress.

    This function:
    1. Marks all other todos as NOT in_progress
    2. Sets the specified todo to in_progress
    3. Updates the updated_at timestamp

    Args:
        todos: List of todo dictionaries
        index: Index of the todo to mark as in_progress

    Returns:
        Updated list of todos
    """
    if index < 0 or index >= len(todos):
        logger.error(f"Invalid todo index: {index} (list has {len(todos)} items)")
        return todos

    # Create a copy to avoid mutating the original
    updated_todos = []
    for i, todo in enumerate(todos):
        todo_copy = todo.copy()
        if i == index:
            todo_copy["status"] = "in_progress"
            todo_copy["updated_at"] = datetime.now().isoformat()
            logger.info(f"Marked todo {index} as in_progress: {todo_copy['content']}")
        elif todo_copy.get("status") == "in_progress":
            # Mark other in_progress todos as pending
            todo_copy["status"] = "pending"
            logger.debug(f"Reset todo {i} to pending: {todo_copy['content']}")

        updated_todos.append(todo_copy)

    return updated_todos


def mark_completed(todos: List[Dict[str, Any]], index: int) -> List[Dict[str, Any]]:
    """Mark a specific todo as completed.

    Updates the status and timestamp for the specified todo.

    Args:
        todos: List of todo dictionaries
        index: Index of the todo to mark as completed

    Returns:
        Updated list of todos
    """
    if index < 0 or index >= len(todos):
        logger.error(f"Invalid todo index: {index} (list has {len(todos)} items)")
        return todos

    # Create a copy to avoid mutating the original
    updated_todos = []
    for i, todo in enumerate(todos):
        todo_copy = todo.copy()
        if i == index:
            todo_copy["status"] = "completed"
            todo_copy["updated_at"] = datetime.now().isoformat()
            logger.info(f"Marked todo {index} as completed: {todo_copy['content']}")

        updated_todos.append(todo_copy)

    return updated_todos


def add_todo(todos: List[Dict[str, Any]], content: str, activeForm: str, status: str = "pending") -> List[Dict[str, Any]]:
    """Add a new todo to the list.

    Args:
        todos: Existing list of todo dictionaries
        content: Description of the new task
        activeForm: Present continuous form of the task
        status: Initial status (default: "pending")

    Returns:
        Updated list of todos with new todo appended
    """
    new_todo = {
        "content": content,
        "activeForm": activeForm,
        "status": status,
        "id": str(uuid.uuid4()),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    updated_todos = todos + [new_todo]
    logger.info(f"Added new todo: {content}")

    return updated_todos


def remove_todo(todos: List[Dict[str, Any]], index: int) -> List[Dict[str, Any]]:
    """Remove a todo from the list.

    Args:
        todos: List of todo dictionaries
        index: Index of the todo to remove

    Returns:
        Updated list of todos with specified todo removed
    """
    if index < 0 or index >= len(todos):
        logger.error(f"Invalid todo index: {index} (list has {len(todos)} items)")
        return todos

    todo_content = todos[index].get("content", "Unknown")
    updated_todos = todos[:index] + todos[index + 1:]
    logger.info(f"Removed todo {index}: {todo_content}")

    return updated_todos


def get_next_pending_todo(todos: List[Dict[str, Any]]) -> Optional[int]:
    """Find the index of the first pending todo.

    Args:
        todos: List of todo dictionaries

    Returns:
        Index of first pending todo, or None if no pending todos exist
    """
    for i, todo in enumerate(todos):
        if todo.get("status") == "pending":
            return i

    return None


def extract_todos_from_messages(messages: List, agent_name: str) -> Optional[List[Dict[str, Any]]]:
    """Extract todos from TodoWrite tool calls in agent messages.

    Scans through agent messages to find TodoWrite tool calls and returns
    the most recent todo list update. This allows us to capture the actual
    todo updates made by agents during their execution.

    Similar to how planner extracts create_plan tool calls from messages.

    Args:
        messages: List of messages from agent execution result
        agent_name: Name of the agent for logging purposes

    Returns:
        List of todo dictionaries from the most recent TodoWrite call,
        or None if no TodoWrite tool calls were found

    Example:
        >>> updated_todos = extract_todos_from_messages(
        ...     result.update.get("messages", []),
        ...     "coder"
        ... )
        >>> if updated_todos:
        ...     todos_update = checkin_todos("coder", updated_todos)
    """
    # Iterate through messages in reverse order to find the most recent TodoWrite call
    for message in reversed(messages):
        # Check if this message has tool calls
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tool_call in message.tool_calls:
                if tool_call.get("name") == "TodoWrite":
                    # Found a TodoWrite tool call, extract the todos
                    logger.info(f"[{agent_name}] Found TodoWrite tool call in agent messages")

                    # The args contain the todos parameter
                    todos = tool_call.get("args", {}).get("todos")

                    if todos and isinstance(todos, list):
                        logger.info(f"[{agent_name}] Extracted {len(todos)} todos from TodoWrite tool call")
                        return todos
                    else:
                        logger.warning(f"[{agent_name}] TodoWrite tool call found but todos data is invalid")
                        return None

    # No TodoWrite calls found
    logger.debug(f"[{agent_name}] No TodoWrite tool calls found in agent messages")
    return None
