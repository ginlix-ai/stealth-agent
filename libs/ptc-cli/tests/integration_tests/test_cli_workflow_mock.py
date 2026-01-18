"""Integration tests for CLI workflows."""

from unittest.mock import AsyncMock, Mock

import pytest

from ptc_cli.commands.slash import handle_command
from ptc_cli.core.state import SessionState
from ptc_cli.display.tokens import TokenTracker
from ptc_cli.input.file_mentions import parse_file_mentions


class TestSlashCommandWorkflow:
    """Integration tests for slash command workflow."""

    @pytest.fixture
    def token_tracker(self):
        """Create a mock token tracker."""
        tracker = Mock(spec=TokenTracker)
        tracker.display = Mock()
        return tracker

    @pytest.fixture
    def session_state(self):
        """Create a session state."""
        return SessionState()

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent."""
        return Mock()

    @pytest.mark.asyncio
    async def test_help_command_workflow(self, mock_agent, token_tracker, session_state):
        """Test /help command workflow."""
        result = await handle_command("/help", mock_agent, token_tracker, session_state)

        assert result == "handled"

    @pytest.mark.asyncio
    async def test_tokens_command_workflow(self, mock_agent, token_tracker, session_state):
        """Test /tokens command workflow."""
        result = await handle_command("/tokens", mock_agent, token_tracker, session_state)

        assert result == "handled"
        token_tracker.display.assert_called_once()

    @pytest.mark.asyncio
    async def test_exit_command_workflow(self, mock_agent, token_tracker, session_state):
        """Test /exit command workflow."""
        result = await handle_command("/exit", mock_agent, token_tracker, session_state)

        assert result == "exit"

    @pytest.mark.asyncio
    async def test_q_command_workflow(self, mock_agent, token_tracker, session_state):
        """Test /q command workflow."""
        result = await handle_command("/q", mock_agent, token_tracker, session_state)

        assert result == "exit"

    @pytest.mark.asyncio
    async def test_clear_command_workflow(self, mock_agent, token_tracker, session_state):
        """Test /clear command workflow."""
        original_thread_id = session_state.thread_id

        result = await handle_command("/clear", mock_agent, token_tracker, session_state)

        assert result == "handled"
        # Thread ID should be different after reset
        assert session_state.thread_id != original_thread_id

    @pytest.mark.asyncio
    async def test_unknown_command_workflow(self, mock_agent, token_tracker, session_state):
        """Test unknown command workflow."""
        result = await handle_command("/unknown", mock_agent, token_tracker, session_state)

        assert result == "handled"

    @pytest.mark.asyncio
    async def test_files_command_without_sandbox(self, mock_agent, token_tracker, session_state):
        """Test /files command without active sandbox."""
        result = await handle_command("/files", mock_agent, token_tracker, session_state, session=None)

        assert result == "handled"

    @pytest.mark.asyncio
    async def test_files_command_with_sandbox(self, mock_agent, token_tracker, session_state):
        """Test /files command with active sandbox."""
        mock_session = Mock()
        mock_sandbox = Mock()
        mock_sandbox.aglob_files = AsyncMock(return_value=[
            "/home/daytona/file1.txt",
            "/home/daytona/src/file2.py",
        ])
        mock_session.sandbox = mock_sandbox
        mock_session.get_sandbox = AsyncMock(return_value=mock_sandbox)

        result = await handle_command("/files", mock_agent, token_tracker, session_state, session=mock_session)

        assert result == "handled"
        mock_session.get_sandbox.assert_called_once()
        mock_sandbox.aglob_files.assert_awaited_once_with("**/*", path=".")

    @pytest.mark.asyncio
    async def test_view_command_without_sandbox(self, mock_agent, token_tracker, session_state):
        """Test /view command without active sandbox."""
        result = await handle_command("/view file.txt", mock_agent, token_tracker, session_state, session=None)

        assert result == "handled"

    @pytest.mark.asyncio
    async def test_view_command_with_sandbox(self, mock_agent, token_tracker, session_state):
        """Test /view command with active sandbox."""
        mock_session = Mock()
        mock_sandbox = Mock()
        mock_sandbox.normalize_path = Mock(return_value="/home/daytona/file.txt")
        mock_sandbox.aread_file_text = AsyncMock(return_value="File content here")
        mock_session.sandbox = mock_sandbox
        mock_session.get_sandbox = AsyncMock(return_value=mock_sandbox)

        result = await handle_command("/view file.txt", mock_agent, token_tracker, session_state, session=mock_session)

        assert result == "handled"
        mock_sandbox.normalize_path.assert_called_once_with("file.txt")
        mock_sandbox.aread_file_text.assert_awaited_once_with("/home/daytona/file.txt")

    @pytest.mark.asyncio
    async def test_copy_command_without_sandbox(self, mock_agent, token_tracker, session_state):
        """Test /copy command without active sandbox."""
        result = await handle_command("/copy file.txt", mock_agent, token_tracker, session_state, session=None)

        assert result == "handled"

    @pytest.mark.asyncio
    async def test_download_command_without_sandbox(self, mock_agent, token_tracker, session_state):
        """Test /download command without active sandbox."""
        result = await handle_command("/download file.txt", mock_agent, token_tracker, session_state, session=None)

        assert result == "handled"

    @pytest.mark.asyncio
    async def test_case_insensitive_commands(self, mock_agent, token_tracker, session_state):
        """Test commands are case-insensitive."""
        result1 = await handle_command("/HELP", mock_agent, token_tracker, session_state)
        assert result1 == "handled"

        result2 = await handle_command("/Help", mock_agent, token_tracker, session_state)
        assert result2 == "handled"

        result3 = await handle_command("/EXIT", mock_agent, token_tracker, session_state)
        assert result3 == "exit"


class TestFileMentionParsingWorkflow:
    """Integration tests for file mention parsing workflow."""

    def test_parse_single_file_mention(self):
        """Test parsing single file mention."""
        text = "Read @file.txt and analyze it"

        original_text, paths = parse_file_mentions(text)

        assert original_text == text
        assert paths == ["file.txt"]

    def test_parse_multiple_file_mentions(self):
        """Test parsing multiple file mentions."""
        text = "Compare @file1.txt with @file2.txt and @file3.txt"

        original_text, paths = parse_file_mentions(text)

        assert original_text == text
        assert paths == ["file1.txt", "file2.txt", "file3.txt"]

    def test_parse_file_with_path(self):
        """Test parsing file mention with path."""
        text = "Read @src/main.py"

        original_text, paths = parse_file_mentions(text)

        assert original_text == text
        assert paths == ["src/main.py"]

    def test_parse_file_with_spaces(self):
        """Test parsing file mention with escaped spaces."""
        text = r"Read @my\ file.txt"

        original_text, paths = parse_file_mentions(text)

        assert original_text == text
        assert paths == ["my file.txt"]

    def test_parse_no_file_mentions(self):
        """Test parsing text with no file mentions."""
        text = "This is just regular text"

        original_text, paths = parse_file_mentions(text)

        assert original_text == text
        assert paths == []

    def test_parse_empty_text(self):
        """Test parsing empty text."""
        text = ""

        original_text, paths = parse_file_mentions(text)

        assert original_text == ""
        assert paths == []

    def test_parse_complex_paths(self):
        """Test parsing complex file paths."""
        text = "Check @src/utils/helper.py and @tests/unit/test_helper.py"

        original_text, paths = parse_file_mentions(text)

        assert original_text == text
        assert paths == ["src/utils/helper.py", "tests/unit/test_helper.py"]

    def test_parse_file_with_dots(self):
        """Test parsing file with dots in name."""
        text = "Read @config.yaml and @setup.cfg"

        original_text, paths = parse_file_mentions(text)

        assert original_text == text
        assert paths == ["config.yaml", "setup.cfg"]

    def test_parse_preserves_original_text(self):
        """Test that parsing preserves the original text unchanged."""
        text = "Read @file1.txt and @file2.txt for analysis"

        original_text, paths = parse_file_mentions(text)

        # Original text should be unchanged
        assert original_text == text
        assert paths == ["file1.txt", "file2.txt"]
