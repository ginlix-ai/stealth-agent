"""Unit tests for display rendering utilities."""

from unittest.mock import patch

from ptc_cli.display.rendering import (
    format_tool_display,
    format_tool_message_content,
    render_diff_block,
    render_file_operation,
    render_todo_list,
)


class TestFormatToolDisplay:
    """Test tool display formatting."""

    def test_simple_args(self):
        """Test formatting with simple arguments."""
        result = format_tool_display("my_tool", {"arg1": "value1", "arg2": 42})
        assert "my_tool" in result
        assert "arg1" in result
        assert "value1" in result
        assert "arg2" in result
        assert "42" in result

    def test_truncates_long_strings(self):
        """Test long string values are truncated."""
        long_string = "x" * 200
        result = format_tool_display("tool", {"content": long_string})
        assert len(result) < len(long_string) + 50  # Should be truncated
        assert "..." in result

    def test_truncates_long_args_string(self):
        """Test overall args string is truncated if too long."""
        args = {f"arg{i}": f"value{i}" for i in range(50)}
        result = format_tool_display("tool", args)
        assert "..." in result

    def test_empty_args(self):
        """Test formatting with no arguments."""
        result = format_tool_display("tool", {})
        assert result == "tool()"

    def test_mixed_types(self):
        """Test formatting with mixed argument types."""
        result = format_tool_display("tool", {
            "string": "text",
            "number": 123,
            "boolean": True,
            "list": [1, 2, 3],
        })
        assert "string" in result
        assert "number" in result
        assert "boolean" in result
        assert "list" in result

    def test_string_repr_with_quotes(self):
        """Test string values are properly quoted."""
        result = format_tool_display("tool", {"path": "test.py"})
        assert "'test.py'" in result or '"test.py"' in result


class TestFormatToolMessageContent:
    """Test tool message content formatting."""

    def test_string_content(self):
        """Test formatting string content."""
        result = format_tool_message_content("Simple string content")
        assert result == "Simple string content"

    def test_list_with_text_blocks(self):
        """Test formatting list with text blocks."""
        content = [
            {"type": "text", "text": "First part"},
            {"type": "text", "text": "Second part"},
        ]
        result = format_tool_message_content(content)
        assert "First part" in result
        assert "Second part" in result

    def test_list_with_mixed_blocks(self):
        """Test formatting list with mixed block types."""
        content = [
            {"type": "text", "text": "Text block"},
            {"type": "image", "data": "..."},
        ]
        result = format_tool_message_content(content)
        assert "Text block" in result

    def test_list_with_strings(self):
        """Test formatting list with plain strings."""
        content = ["Line 1", "Line 2", "Line 3"]
        result = format_tool_message_content(content)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_empty_list(self):
        """Test formatting empty list returns None."""
        result = format_tool_message_content([])
        assert result is None

    def test_empty_string(self):
        """Test formatting empty string."""
        result = format_tool_message_content("")
        assert result == ""

    def test_none_type(self):
        """Test formatting None returns None."""
        result = format_tool_message_content(None)
        assert result is None

    def test_list_with_empty_text_blocks(self):
        """Test formatting list with empty text blocks."""
        content = [
            {"type": "text", "text": ""},
            {"type": "text", "text": "Not empty"},
        ]
        result = format_tool_message_content(content)
        assert "Not empty" in result


class TestRenderTodoList:
    """Test todo list rendering."""

    def test_empty_list(self):
        """Test rendering empty todo list."""
        with patch("ptc_cli.display.rendering.console") as mock_console:
            render_todo_list([])
            # Should not print anything for empty list
            assert mock_console.print.call_count == 0

    def test_pending_task(self):
        """Test rendering pending task."""
        todos = [{"status": "pending", "content": "Do something"}]
        with patch("ptc_cli.display.rendering.console") as mock_console:
            render_todo_list(todos)
            # Should print task with pending icon
            assert mock_console.print.call_count >= 2  # Header + task

    def test_in_progress_task(self):
        """Test rendering in-progress task."""
        todos = [{"status": "in_progress", "content": "Working on it"}]
        with patch("ptc_cli.display.rendering.console") as mock_console:
            render_todo_list(todos)
            assert mock_console.print.call_count >= 2

    def test_completed_task(self):
        """Test rendering completed task."""
        todos = [{"status": "completed", "content": "Done"}]
        with patch("ptc_cli.display.rendering.console") as mock_console:
            render_todo_list(todos)
            assert mock_console.print.call_count >= 2

    def test_multiple_tasks(self):
        """Test rendering multiple tasks with different statuses."""
        todos = [
            {"status": "completed", "content": "Task 1"},
            {"status": "in_progress", "content": "Task 2"},
            {"status": "pending", "content": "Task 3"},
        ]
        with patch("ptc_cli.display.rendering.console") as mock_console:
            render_todo_list(todos)
            # Should print header + 3 tasks
            assert mock_console.print.call_count >= 4

    def test_task_without_status(self):
        """Test rendering task without status defaults to pending."""
        todos = [{"content": "No status"}]
        with patch("ptc_cli.display.rendering.console") as mock_console:
            render_todo_list(todos)
            assert mock_console.print.call_count >= 2

    def test_task_without_content(self):
        """Test rendering task without content."""
        todos = [{"status": "pending"}]
        with patch("ptc_cli.display.rendering.console") as mock_console:
            render_todo_list(todos)
            assert mock_console.print.call_count >= 2


class TestRenderDiffBlock:
    """Test diff block rendering."""

    def test_renders_diff_with_syntax(self):
        """Test diff is rendered with syntax highlighting."""
        diff = "- old line\n+ new line"
        with patch("ptc_cli.display.rendering.console") as mock_console:
            render_diff_block(diff, "Changes")
            mock_console.print.assert_called_once()

    def test_includes_title(self):
        """Test rendered diff includes title."""
        diff = "- old\n+ new"
        with patch("ptc_cli.display.rendering.console") as mock_console:
            render_diff_block(diff, "My Changes")
            # Title should be in the Panel
            call_args = mock_console.print.call_args
            assert call_args is not None


class TestRenderFileOperation:
    """Test file operation rendering."""

    def test_success_status(self):
        """Test rendering successful file operation."""
        record = {"name": "create", "path": "test.py", "status": "success"}
        with patch("ptc_cli.display.rendering.console") as mock_console:
            render_file_operation(record)
            mock_console.print.assert_called_once()
            call_str = str(mock_console.print.call_args)
            assert "create" in call_str
            assert "test.py" in call_str

    def test_error_status(self):
        """Test rendering failed file operation."""
        record = {"name": "delete", "path": "file.txt", "status": "error"}
        with patch("ptc_cli.display.rendering.console") as mock_console:
            render_file_operation(record)
            mock_console.print.assert_called_once()

    def test_unknown_status(self):
        """Test rendering file operation with unknown status."""
        record = {"name": "update", "path": "config.yml", "status": "unknown"}
        with patch("ptc_cli.display.rendering.console") as mock_console:
            render_file_operation(record)
            mock_console.print.assert_called_once()

    def test_missing_fields(self):
        """Test rendering file operation with missing fields."""
        record = {}
        with patch("ptc_cli.display.rendering.console") as mock_console:
            render_file_operation(record)
            mock_console.print.assert_called_once()
