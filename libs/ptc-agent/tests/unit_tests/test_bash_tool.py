"""Tests for bash execution tool."""

from unittest.mock import AsyncMock

import pytest

from ptc_agent.agent.tools.bash import create_execute_bash_tool

# Use mock_async_sandbox from conftest.py for async sandbox methods


class TestExecuteBashTool:
    """Tests for execute_bash tool."""

    @pytest.mark.asyncio
    async def test_execute_bash_success_with_output(self, mock_async_sandbox):
        """Test successful bash command execution with output."""
        mock_async_sandbox.execute_bash_command = AsyncMock(
            return_value={
                "success": True,
                "stdout": "file1.txt\nfile2.txt\nfile3.txt",
                "stderr": "",
                "exit_code": 0,
            }
        )

        execute_bash = create_execute_bash_tool(mock_async_sandbox)
        result = await execute_bash.ainvoke({"command": "ls", "working_dir": "/home/daytona"})

        assert "ERROR" not in result
        assert "file1.txt" in result
        assert "file2.txt" in result
        mock_async_sandbox.execute_bash_command.assert_called_once_with(
            "ls", working_dir="/home/daytona", timeout=120.0, background=False
        )

    @pytest.mark.asyncio
    async def test_execute_bash_success_no_output(self, mock_async_sandbox):
        """Test successful bash command with no output (e.g., mkdir)."""
        mock_async_sandbox.execute_bash_command = AsyncMock(
            return_value={"success": True, "stdout": "", "stderr": "", "exit_code": 0}
        )

        execute_bash = create_execute_bash_tool(mock_async_sandbox)
        result = await execute_bash.ainvoke({"command": "mkdir -p /home/daytona/testdir"})

        assert "ERROR" not in result
        assert "Command completed successfully" in result

    @pytest.mark.asyncio
    async def test_execute_bash_command_failure(self, mock_async_sandbox):
        """Test bash command that fails."""
        mock_async_sandbox.execute_bash_command = AsyncMock(
            return_value={
                "success": False,
                "stdout": "",
                "stderr": "ls: cannot access '/nonexistent': No such file or directory",
                "exit_code": 2,
            }
        )

        execute_bash = create_execute_bash_tool(mock_async_sandbox)
        result = await execute_bash.ainvoke({"command": "ls /nonexistent"})

        assert "ERROR" in result
        assert "exit code 2" in result
        assert "No such file or directory" in result

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("command", "stdout", "expected_in_result"),
        [
            ("cat file.txt | wc -l", "100 lines counted", "100 lines counted"),
            ("echo 'Hello World' > output.txt", "", None),
            (
                "grep -r 'def ' *.py",
                "file1.py:def function1():\nfile2.py:def function2():",
                "function1",
            ),
            (
                "find . -name '*.txt'",
                "./file1.txt\n./subdir/file2.txt\n./subdir/file3.txt",
                "file1.txt",
            ),
            (
                "mkdir -p output && echo 'Done'",
                "Done",
                "Done",
            ),
            ("wc file.txt", "  42  256 1824 file.txt", "42"),
            ("du -sh results/", "4.5M\tresults/", "4.5M"),
            ("cat file.txt", "Line 1\nLine 2\nLine 3", "Line 1"),
            ("head -5 file.txt", "Line 1\nLine 2\nLine 3\nLine 4\nLine 5", "Line 1"),
            ("awk '{print $2}' data.txt", "value1\nvalue2\nvalue3", "value1"),
        ],
        ids=[
            "pipe",
            "redirect",
            "grep",
            "find",
            "chained",
            "wc",
            "du",
            "cat",
            "head",
            "awk",
        ],
    )
    async def test_execute_bash_various_commands(
        self, mock_async_sandbox, command, stdout, expected_in_result
    ):
        """Test various bash commands execute successfully."""
        mock_async_sandbox.execute_bash_command = AsyncMock(
            return_value={"success": True, "stdout": stdout, "stderr": "", "exit_code": 0}
        )

        execute_bash = create_execute_bash_tool(mock_async_sandbox)
        result = await execute_bash.ainvoke({"command": command})

        assert "ERROR" not in result
        if expected_in_result:
            assert expected_in_result in result

    @pytest.mark.asyncio
    async def test_execute_bash_with_working_dir(self, mock_async_sandbox):
        """Test bash command with custom working directory."""
        mock_async_sandbox.execute_bash_command = AsyncMock(
            return_value={"success": True, "stdout": "file.txt", "stderr": "", "exit_code": 0}
        )

        execute_bash = create_execute_bash_tool(mock_async_sandbox)
        result = await execute_bash.ainvoke({"command": "ls", "working_dir": "/home/daytona/results"})

        assert "ERROR" not in result
        mock_async_sandbox.execute_bash_command.assert_called_once_with(
            "ls", working_dir="/home/daytona/results", timeout=120.0, background=False
        )

    @pytest.mark.asyncio
    async def test_execute_bash_exception(self, mock_async_sandbox):
        """Test bash command that raises an exception."""
        mock_async_sandbox.execute_bash_command = AsyncMock(
            side_effect=Exception("Sandbox connection error")
        )

        execute_bash = create_execute_bash_tool(mock_async_sandbox)
        result = await execute_bash.ainvoke({"command": "ls"})

        assert "ERROR" in result
        assert "Failed to execute bash command" in result
        assert "Sandbox connection error" in result
