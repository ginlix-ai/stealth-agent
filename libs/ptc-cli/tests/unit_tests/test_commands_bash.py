"""Unit tests for bash command execution."""

from unittest.mock import AsyncMock, patch

import pytest

from ptc_cli.commands.bash import execute_bash_command


class TestExecuteBashCommand:
    """Test bash command execution in sandbox."""

    @pytest.mark.asyncio
    async def test_empty_command_shows_warning(self):
        """Test empty command shows warning message."""
        mock_sandbox = AsyncMock()
        with patch("ptc_cli.commands.bash.console") as mock_console:
            await execute_bash_command("!", sandbox=mock_sandbox)
            mock_console.print.assert_called()
            assert any("No command specified" in str(call) for call in mock_console.print.call_args_list)
            # Sandbox should not be called for empty command
            mock_sandbox.execute_bash_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_sandbox_shows_error(self):
        """Test that missing sandbox shows error message."""
        with patch("ptc_cli.commands.bash.console") as mock_console:
            await execute_bash_command("!ls", sandbox=None)
            calls = [str(call) for call in mock_console.print.call_args_list]
            assert any("Sandbox not initialized" in call for call in calls)

    @pytest.mark.asyncio
    async def test_successful_command_execution(self):
        """Test successful command execution prints output."""
        mock_sandbox = AsyncMock()
        mock_sandbox.execute_bash_command.return_value = {
            "success": True,
            "stdout": "test output",
            "stderr": "",
            "exit_code": 0,
            "bash_id": "test-123",
        }

        with patch("ptc_cli.commands.bash.console") as mock_console:
            await execute_bash_command("!echo test", sandbox=mock_sandbox)

            # Verify sandbox.execute_bash_command was called correctly
            mock_sandbox.execute_bash_command.assert_called_once_with(
                "echo test",
                timeout=60,
            )

            # Verify output was printed
            calls = [str(call) for call in mock_console.print.call_args_list]
            assert any("test output" in call for call in calls)

    @pytest.mark.asyncio
    async def test_command_with_stderr(self):
        """Test command with stderr output."""
        mock_sandbox = AsyncMock()
        mock_sandbox.execute_bash_command.return_value = {
            "success": False,
            "stdout": "",
            "stderr": "error message",
            "exit_code": 1,
            "bash_id": "test-123",
        }

        with patch("ptc_cli.commands.bash.console") as mock_console:
            await execute_bash_command("!invalid_command", sandbox=mock_sandbox)

            # Should print stderr (with style="red")
            calls = [str(call) for call in mock_console.print.call_args_list]
            assert any("error message" in call for call in calls)

    @pytest.mark.asyncio
    async def test_command_timeout_handling(self):
        """Test command timeout is handled gracefully."""
        mock_sandbox = AsyncMock()
        mock_sandbox.execute_bash_command.side_effect = TimeoutError("Command timed out")

        with patch("ptc_cli.commands.bash.console") as mock_console:
            await execute_bash_command("!sleep 100", sandbox=mock_sandbox)

            # Should print timeout message
            calls = [str(call) for call in mock_console.print.call_args_list]
            assert any("timed out" in call.lower() for call in calls)

    @pytest.mark.asyncio
    async def test_generic_error_handling(self):
        """Test generic error is handled gracefully."""
        mock_sandbox = AsyncMock()
        mock_sandbox.execute_bash_command.side_effect = Exception("Unexpected error")

        with patch("ptc_cli.commands.bash.console") as mock_console:
            await execute_bash_command("!bad_command", sandbox=mock_sandbox)

            # Should print error message
            calls = [str(call) for call in mock_console.print.call_args_list]
            assert any("error" in call.lower() for call in calls)

    @pytest.mark.asyncio
    async def test_non_zero_exit_code_displayed(self):
        """Test non-zero exit code is displayed."""
        mock_sandbox = AsyncMock()
        mock_sandbox.execute_bash_command.return_value = {
            "success": False,
            "stdout": "",
            "stderr": "",
            "exit_code": 42,
            "bash_id": "test-123",
        }

        with patch("ptc_cli.commands.bash.console") as mock_console:
            await execute_bash_command("!exit 42", sandbox=mock_sandbox)

            # Should print exit code
            calls = [str(call) for call in mock_console.print.call_args_list]
            assert any("42" in call for call in calls)

    @pytest.mark.asyncio
    async def test_strips_leading_exclamation(self):
        """Test that leading ! is properly stripped."""
        mock_sandbox = AsyncMock()
        mock_sandbox.execute_bash_command.return_value = {
            "success": True,
            "stdout": "",
            "stderr": "",
            "exit_code": 0,
            "bash_id": "test-123",
        }

        with patch("ptc_cli.commands.bash.console"):
            await execute_bash_command("!ls -la", sandbox=mock_sandbox)

            # Should call with "ls -la" not "!ls -la"
            call_args = mock_sandbox.execute_bash_command.call_args
            assert call_args[0][0] == "ls -la"
