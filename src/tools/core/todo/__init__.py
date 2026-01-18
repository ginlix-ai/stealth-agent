"""Todo tracking system for multi-agent workflows.

This package provides a comprehensive todo management system for tracking
agent task progress throughout workflow execution.

Main Components:
- TodoWrite: LangChain tool for agents to manage their todo lists
- TodoItem, TodoStatus: Data models for todo items
- Manager functions: checkout_todos, checkin_todos, extract_todos_from_messages
- Helper functions: mark_in_progress, mark_completed, add_todo, remove_todo, etc.

Usage:
    from src.tools.core.todo import TodoWrite, checkout_todos, checkin_todos
"""

# Tool
from .tool import TodoWrite

# Data models and validation
from .types import (
    TodoItem,
    TodoStatus,
    validate_single_in_progress,
    validate_todo_list_dict,
)

# Manager functions
from .manager import (
    checkout_todos,
    checkin_todos,
    extract_todos_from_messages,
    mark_in_progress,
    mark_completed,
    add_todo,
    remove_todo,
    get_next_pending_todo,
)

__all__ = [
    # Tool
    "TodoWrite",
    # Data models
    "TodoItem",
    "TodoStatus",
    "validate_single_in_progress",
    "validate_todo_list_dict",
    # Manager functions
    "checkout_todos",
    "checkin_todos",
    "extract_todos_from_messages",
    "mark_in_progress",
    "mark_completed",
    "add_todo",
    "remove_todo",
    "get_next_pending_todo",
]
