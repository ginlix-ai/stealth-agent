import logging
from typing import List, Dict, Any, Annotated
from langchain_core.tools import tool
from pydantic import Field

from .types import validate_todo_list_dict

logger = logging.getLogger(__name__)


@tool(parse_docstring=True)
def TodoWrite(
    todos: Annotated[
        List[Dict[str, Any]],
        Field(
            description=(
                "Complete collection of todo items. "
                "PARAMETER NAME MUST BE 'todos' (plural), not 'todo' or 'todo_list'. "
                "Each item requires: content (str), activeForm (str), status (str)"
            )
        )
    ]
) -> str:
    """Create or update todos for tracking task progress throughout execution.

    **PARAMETER NAME**: The parameter MUST be named `todos` (plural). Common mistakes:
    - ✗ WRONG: `todo=...` (singular)
    - ✗ WRONG: `todo_list=...`
    - ✓ CORRECT: `todos=...` (plural)

    **WRITE-ONLY INTERFACE**: This tool is write-only with no read capability. Agents cannot
    query the current state - they must maintain the complete collection in their working memory
    and pass the full updated collection with each call.

    **PURPOSE**: Helps agents organize multi-step tasks, track progress systematically, and
    provide transparency to users about current work status.

    Each item MUST include these fields:
    - content (str): Imperative description of the task (e.g., "Fetch market data")
    - activeForm (str): Present continuous form shown during execution (e.g., "Fetching market data")
    - status (str): One of "pending", "in_progress", or "completed"

    **CRITICAL RULES**:
    1. **Complete Replacement**: Each call completely REPLACES the previous collection. Always pass
       the ENTIRE collection, not just changes.
    2. **Single Focus**: Exactly ONE task must have status "in_progress" at any time. Never zero,
       never multiple.
    3. **Immediate Updates**: Mark tasks "completed" IMMEDIATELY after finishing them. Do not batch
       multiple completions.
    4. **Dynamic Management**: Add new tasks discovered during execution. Remove tasks that become
       irrelevant.
    5. **State Tracking**: You cannot read back the state. Track it in memory throughout execution.

    **WHEN TO USE**:
    - Multi-step tasks requiring 3+ distinct operations
    - Complex workflows with dependencies between steps
    - Long-running tasks where progress visibility is important
    - Tasks that may discover additional subtasks during execution

    Args:
        todos: Complete collection of items, each with content, activeForm, and status.
               Parameter name is 'todos' (plural), not 'todo' or 'todo_list'.

    Returns:
        str: Success confirmation message

    Examples:
        # Initial planning with multiple steps
        # NOTE: Use 'todos=' (plural) as the parameter name
        TodoWrite(todos=[
            {"content": "Search for company financial reports", "activeForm": "Searching for company financial reports", "status": "in_progress"},
            {"content": "Extract key financial metrics", "activeForm": "Extracting key financial metrics", "status": "pending"},
            {"content": "Verify data accuracy and completeness", "activeForm": "Verifying data accuracy and completeness", "status": "pending"}
        ])

        # First task completed, start second task
        TodoWrite(todos=[
            {"content": "Search for company financial reports", "activeForm": "Searching for company financial reports", "status": "completed"},
            {"content": "Extract key financial metrics", "activeForm": "Extracting key financial metrics", "status": "in_progress"},
            {"content": "Verify data accuracy and completeness", "activeForm": "Verifying data accuracy and completeness", "status": "pending"}
        ])

        # Discovered additional subtask during execution - add it
        TodoWrite(todos=[
            {"content": "Search for company financial reports", "activeForm": "Searching for company financial reports", "status": "completed"},
            {"content": "Extract key financial metrics", "activeForm": "Extracting key financial metrics", "status": "completed"},
            {"content": "Verify data accuracy and completeness", "activeForm": "Verifying data accuracy and completeness", "status": "in_progress"},
            {"content": "Cross-reference with industry benchmarks", "activeForm": "Cross-referencing with industry benchmarks", "status": "pending"}
        ])

        # All tasks completed
        TodoWrite(todos=[
            {"content": "Search for company financial reports", "activeForm": "Searching for company financial reports", "status": "completed"},
            {"content": "Extract key financial metrics", "activeForm": "Extracting key financial metrics", "status": "completed"},
            {"content": "Verify data accuracy and completeness", "activeForm": "Verifying data accuracy and completeness", "status": "completed"},
            {"content": "Cross-reference with industry benchmarks", "activeForm": "Cross-referencing with industry benchmarks", "status": "completed"}
        ])
    """
    logger.info(f"Todo list updated with {len(todos)} items")

    # Validate todo format and get errors
    is_valid, validation_errors = validate_todo_list_dict(todos)

    # Log todo statuses for debugging
    status_counts = {"pending": 0, "in_progress": 0, "completed": 0}
    for todo in todos:
        status = todo.get("status", "unknown")
        if status in status_counts:
            status_counts[status] += 1
        logger.debug(f"  - [{status}] {todo.get('content', 'No content')}")

    logger.debug(f"Status summary: {status_counts}")

    # Calculate counts for conditional messaging
    total_count = len(todos)
    completed_count = status_counts["completed"]
    pending_count = status_counts["pending"]
    in_progress_count = status_counts["in_progress"]
    remaining_count = pending_count + in_progress_count

    # Build response message based on completion state
    if completed_count == total_count and total_count > 0:
        # Scenario A: All tasks completed
        response = "✓ All tasks completed! You can now proceed to the next stage or add more tasks if needed."
        logger.info("All todos completed")
    elif remaining_count == 1 and total_count > 1:
        # Scenario B: One task remaining (append to default)
        response = (
            "Todos have been modified successfully. Ensure that you continue to use the todo list to "
            "track your progress. Please proceed with the current tasks if applicable\n\n"
            "💡 Reminder: One task remaining - remember to mark it as completed after finishing it."
        )
        logger.info("One task remaining")
    else:
        # Scenario C: Multiple tasks remaining (default message)
        response = (
            "Todos have been modified successfully. Ensure that you continue to use the todo list to "
            "track your progress. Please proceed with the current tasks if applicable"
        )

    # Append validation warnings if format issues detected
    if not is_valid:
        logger.warning(f"Todo format validation failed: {validation_errors}")
        validation_section = "\n\n⚠️ Format Validation Issues:\n"
        validation_section += "\n".join(f"  - {error}" for error in validation_errors)
        response += validation_section

    return response
