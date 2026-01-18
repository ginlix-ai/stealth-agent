"""Display formatting and rendering utilities for the CLI."""

from rich.panel import Panel

from ptc_cli.core import MAX_ARG_LENGTH, MAX_ERROR_LENGTH, console, get_syntax_theme


def format_tool_display(tool_name: str, args: dict) -> str:
    """Format tool call for display.

    Args:
        tool_name: Name of the tool
        args: Tool arguments

    Returns:
        Formatted string for display
    """
    # Build argument summary
    arg_parts = []
    for key, value in args.items():
        if isinstance(value, str):
            if len(value) > MAX_ARG_LENGTH:
                truncated_value = value[:MAX_ARG_LENGTH] + "..."
                arg_parts.append(f"{key}={truncated_value!r}")
            else:
                arg_parts.append(f"{key}={value!r}")
        else:
            arg_parts.append(f"{key}={value}")

    args_str = ", ".join(arg_parts)
    if len(args_str) > MAX_ARG_LENGTH:
        args_str = args_str[:MAX_ARG_LENGTH] + "..."

    return f"{tool_name}({args_str})"


def truncate_error(error: str, max_length: int = MAX_ERROR_LENGTH) -> str:
    """Truncate error message for display.

    Args:
        error: The error message to truncate
        max_length: Maximum length before truncation

    Returns:
        Truncated error string with '...' if exceeded max_length
    """
    if len(error) <= max_length:
        return error
    return error[:max_length] + "..."


def render_diff_block(diff: str, title: str) -> None:
    """Render a diff block with syntax highlighting.

    Args:
        diff: The diff content
        title: Title for the diff block
    """
    from rich.syntax import Syntax

    syntax = Syntax(diff, "diff", theme=get_syntax_theme(), line_numbers=False)
    console.print(Panel(syntax, title=title, border_style="yellow"))


def format_tool_message_content(content: str | list) -> str | None:
    """Format tool message content for display.

    Args:
        content: Tool message content (string or list)

    Returns:
        Formatted string or None
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Extract text from content blocks
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                text_parts.append(block)
        return "\n".join(text_parts) if text_parts else None
    return None


def render_todo_list(todos: list) -> None:
    """Render a todo list.

    Uses the same display rules as `tui/display.py`:
    - pending/completed show `content`
    - in_progress prefers `activeForm`
    """
    if not todos:
        return

    console.print("📋 Todo List:", style="bold")

    for todo in todos:
        status = todo.get("status", "pending")

        if status == "in_progress":
            text = todo.get("activeForm", todo.get("content", ""))
        else:
            text = todo.get("content", "")

        # Truncate long items for readability
        max_length = 80
        if isinstance(text, str) and len(text) > max_length:
            text = text[: max_length - 3] + "..."

        if status == "completed":
            icon = "[✓]"
            style = "green dim"
        elif status == "in_progress":
            icon = "[→]"
            style = "yellow bold"
        else:
            icon = "[ ]"
            style = "white"

        console.print(f"  {icon} {text}", style=style, markup=False)


def render_file_operation(record: dict) -> None:
    """Render a file operation record.

    Args:
        record: File operation record with name, path, status
    """
    name = record.get("name", "unknown")
    path = record.get("path", "")
    status = record.get("status", "unknown")

    if status == "success":
        icon = "[green]✓[/green]"
    elif status == "error":
        icon = "[red]✗[/red]"
    else:
        icon = "[yellow]→[/yellow]"

    console.print(f"  {icon} {name}: {path}")
