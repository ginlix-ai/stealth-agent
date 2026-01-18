"""Filesystem validation and display utilities."""

import logging
import re

from langchain_core.messages import ToolMessage

from . import FileData

logger = logging.getLogger(__name__)


def format_files_as_tree(files: dict[str, FileData]) -> str:
    """Format files dictionary as a visual tree structure.

    Args:
        files: Dictionary mapping file paths to FileData

    Returns:
        Visual tree representation as string

    Example:
        >>> files = {"/data/test.md": {...}, "/analysis/report.md": {...}}
        >>> print(format_files_as_tree(files))
        Filesystem (2 files):
        /
        ├── data/
        │   └── test.md (10 lines)
        └── analysis/
            └── report.md (25 lines)
    """
    if not files:
        return "Filesystem: (empty)"

    # Build directory structure
    tree = {}
    for path in sorted(files.keys()):
        # Remove leading slash and split path
        parts = path.lstrip('/').split('/')
        current = tree

        # Build nested dict structure
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                # Leaf node (file)
                file_data = files[path]
                line_count = len(file_data.get("content", []))
                current[part] = f"({line_count} lines)"
            else:
                # Directory node
                if part not in current:
                    current[part] = {}
                current = current[part]

    # Format as tree
    def format_tree_recursive(node: dict, prefix: str = "", is_last: bool = True) -> list[str]:
        """Recursively format tree structure."""
        lines = []
        items = list(node.items())

        for i, (name, value) in enumerate(items):
            is_last_item = (i == len(items) - 1)

            # Choose box drawing characters
            if is_last_item:
                connector = "└── "
                extension = "    "
            else:
                connector = "├── "
                extension = "│   "

            # Format current item
            if isinstance(value, dict):
                # Directory
                lines.append(f"{prefix}{connector}{name}/")
                # Recurse into subdirectory
                sublines = format_tree_recursive(value, prefix + extension, is_last_item)
                lines.extend(sublines)
            else:
                # File with line count
                lines.append(f"{prefix}{connector}{name} {value}")

        return lines

    # Build output
    result = [f"Filesystem ({len(files)} file{'s' if len(files) != 1 else ''}):"]
    result.append("/")
    result.extend(format_tree_recursive(tree))

    return "\n".join(result)


def extract_file_operations_from_messages(messages: list) -> list[dict]:
    """Extract write_file tool calls and results from messages using status field.

    Searches messages for write_file ToolMessages to identify which files
    were created by agents during execution. Uses the ToolMessage.status field
    for reliable success/error detection.

    Args:
        messages: List of message objects from agent execution

    Returns:
        List of dicts with file operation info: [{"path": "/data/test.md", "success": True, ...}, ...]

    Example:
        operations = extract_file_operations_from_messages(result["messages"])
        print(f"Agent created {len(operations)} files")
    """
    file_operations = []

    for message in messages:
        # Look for write_file tool results
        if isinstance(message, ToolMessage) and hasattr(message, 'name') and message.name == "write_file":
            try:
                # Use status field for reliable success/error detection
                success = getattr(message, 'status', 'success') == 'success'

                # Extract path from content for logging (works with any file extension)
                content = message.content
                file_path = "unknown"
                if isinstance(content, str):
                    # Match any file with extension (not just .md)
                    match = re.search(r'(/[\w/._-]+\.\w+)', content)
                    if match:
                        file_path = match.group(1)

                file_operations.append({
                    "path": file_path,
                    "success": success,
                    "message": content
                })
            except Exception as e:
                logger.debug(f"Error parsing write_file tool message: {e}")
                continue

    return file_operations


def validate_file_operations(messages: list, agent_name: str) -> tuple[bool, list[str]]:
    """Validate that filesystem-enabled agent created files.

    Checks if agent with filesystem enabled actually used write_file tool.
    Similar to validate_plan_structure() pattern from plan_tool.py.

    Args:
        messages: List of message objects from agent execution
        agent_name: Name of agent being validated (for logging)

    Returns:
        Tuple of (has_files, warnings)
        - has_files: True if agent created at least one file
        - warnings: List of validation warning messages

    Example:
        has_files, warnings = validate_file_operations(result["messages"], "data_agent")
        if not has_files:
            for warning in warnings:
                logger.warning(warning)
    """
    warnings = []

    # Extract file operations
    operations = extract_file_operations_from_messages(messages)

    # Check if any files were created
    successful_ops = [op for op in operations if op.get("success", False)]

    if len(successful_ops) == 0:
        warnings.append(
            f"{agent_name} has filesystem enabled but did not create any files. "
            f"This may indicate the agent didn't follow instructions to use write_file."
        )
        return False, warnings

    # Optional: Check for failed operations
    failed_ops = [op for op in operations if not op.get("success", True)]
    if failed_ops:
        warnings.append(
            f"{agent_name} had {len(failed_ops)} failed write_file operation(s). "
            f"Check logs for details."
        )

    return True, warnings


def validate_filesystem_and_generate_feedback(
    messages: list,
    agent_name: str,
    attempts_remaining: int,
    max_retries: int
) -> tuple[bool, str]:
    """
    Validate filesystem documentation and generate retry feedback.

    Checks if agent created files and generates user-friendly error message
    for retry attempts. Uses countdown model (3→0) for attempts remaining.

    Args:
        messages: List of message objects from agent execution
        agent_name: Name of agent being validated
        attempts_remaining: Number of retry attempts remaining (countdown: 3→2→1→0)
        max_retries: Maximum retry attempts allowed (typically 3)

    Returns:
        Tuple of (is_valid, feedback_message)
        - is_valid: True if agent created at least one file
        - feedback_message: Empty if valid, error message with counter if invalid

    Example:
        is_valid, feedback = validate_filesystem_and_generate_feedback(
            result["messages"], "coder", 2, 3  # 2 attempts remaining
        )
        if not is_valid:
            # Append feedback and retry
            input_messages.append(HumanMessage(content=feedback, name="validation_feedback"))
    """
    # Reuse existing validation logic
    has_files, warnings = validate_file_operations(messages, agent_name)

    if has_files:
        return True, ""

    # Calculate attempt number for display (1-indexed)
    attempt_number = max_retries - attempts_remaining + 1

    # Generate feedback similar to planner validation pattern (nodes.py:274-276)
    feedback = (
        f"**Attempt {attempt_number}/{max_retries} ({attempts_remaining} remaining)**\n\n"
        f"**Filesystem Documentation Required**\n\n"
        f"You completed your analysis but did not document the results in the filesystem. "
        f"This is required for other agents to access your findings.\n\n"
        f"**Please:**\n"
        f"1. Use the `write_file()` tool to save your analysis results\n"
        f"2. Choose appropriate file names (e.g., 'technical_analysis.md', 'stock_data.json')\n"
        f"3. Organize content in a structured format (Markdown for reports, JSON for data)\n\n"
        f"**Required:** Create at least one file with your findings before completing this step."
    )

    return False, feedback


def detect_file_changes_for_events(
    previous_files: dict[str, FileData],
    new_files: dict[str, FileData],
    agent_name: str
) -> list[dict]:
    """
    Detect file changes between two file states and generate file_operation event payloads.

    This function compares two file state dictionaries and generates SSE-compatible
    file_operation events for streaming to the frontend. Useful for subgraphs or
    agents that create files programmatically (not via tool calls).

    Args:
        previous_files: Files before operation (from state.get("files", {}))
        new_files: Files after operation (from result.get("files", {}))
        agent_name: Name of agent that made the changes (e.g., "researcher")

    Returns:
        List of file_operation event payloads compatible with streaming handler.
        Each event has structure matching tool-based file operations:
        {
            "agent": str,
            "operation": "write_file" | "delete_file",
            "file_path": str,
            "tool_call_id": None,  # Synthetic events have no tool call
            "timestamp": str,  # ISO 8601 format
            "content": str  # Only for write_file operations
        }

    Example:
        >>> previous = {}
        >>> new = {"/analysis/report.md": {"content": ["# Report"], "path": "/analysis/report.md"}}
        >>> events = detect_file_changes_for_events(previous, new, "researcher")
        >>> len(events)
        1
        >>> events[0]["operation"]
        'write_file'
    """
    from datetime import datetime, timezone

    file_operation_events = []

    # Detect new/modified files (write_file operations)
    for file_path, file_data in new_files.items():
        if file_data is not None:  # Not a deletion
            # Check if this is a new file or modified file
            if file_path not in previous_files:
                # New file created
                content_lines = file_data.get("content", [])
                content_str = "\n".join(content_lines) if isinstance(content_lines, list) else str(content_lines)

                event_payload = {
                    "agent": agent_name,
                    "operation": "write_file",
                    "file_path": file_path,
                    "tool_call_id": None,  # Synthetic event, no tool call
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "content": content_str
                }
                file_operation_events.append(event_payload)

    # Detect deleted files (files in previous but not in new, or set to None)
    for file_path in previous_files.keys():
        if file_path not in new_files or new_files.get(file_path) is None:
            # File was deleted
            event_payload = {
                "agent": agent_name,
                "operation": "delete_file",
                "file_path": file_path,
                "tool_call_id": None,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            file_operation_events.append(event_payload)

    return file_operation_events


def string_to_file_data(
    content: str,
    created_at: str | None = None,
    modified_at: str | None = None
) -> FileData:
    """
    Convert a string to FileData format (list of lines).

    This is the inverse of _file_data_to_string() and is used for
    loading files from database back into state. Ensures bidirectional
    conversion between database storage (string) and state format (list[str]).

    Args:
        content: String content to convert
        created_at: Optional creation timestamp (ISO 8601)
        modified_at: Optional modification timestamp (ISO 8601)

    Returns:
        FileData with content as list[str]

    Example:
        >>> db_content = "Line 1\\nLine 2\\nLine 3"
        >>> file_data = string_to_file_data(db_content)
        >>> file_data['content']
        ['Line 1', 'Line 2', 'Line 3']
        >>> len(file_data['content'])
        3
    """
    from . import _create_file_data

    # Use _create_file_data for consistency (handles line chunking)
    file_data = _create_file_data(content, created_at=created_at)

    # Override modified_at if provided (created_at is already set by _create_file_data)
    if modified_at:
        file_data['modified_at'] = modified_at

    return file_data
