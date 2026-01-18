"""Unit tests for slash command handlers."""

from unittest.mock import Mock, patch

import pytest

from ptc_cli.commands.slash import (
    _handle_copy_command,
    _handle_download_command,
    _handle_files_command,
    _handle_view_command,
    _normalize_path,
    _render_tree,
    handle_command,
)


class TestNormalizePath:
    """Test path normalization."""

    def test_removes_home_prefix(self):
        """Test that /home/daytona/ prefix is removed."""
        assert _normalize_path("/home/daytona/test.py") == "test.py"
        assert _normalize_path("/home/daytona/src/main.py") == "src/main.py"

    def test_preserves_other_paths(self):
        """Test that other paths are unchanged."""
        assert _normalize_path("/etc/config") == "/etc/config"
        assert _normalize_path("relative/path") == "relative/path"


class TestRenderTree:
    """Test tree rendering."""

    def test_single_file(self):
        """Test rendering a single file."""
        files = ["test.py"]
        result = _render_tree(files)
        assert len(result) == 1
        assert "test.py" in result[0]

    def test_nested_files(self):
        """Test rendering nested directory structure."""
        files = ["src/main.py", "src/utils.py", "tests/test_main.py"]
        result = _render_tree(files)
        assert any("src" in line for line in result)
        assert any("tests" in line for line in result)
        assert any("main.py" in line for line in result)

    def test_empty_list(self):
        """Test rendering empty file list."""
        files = []
        result = _render_tree(files)
        assert result == []


class TestHandleFilesCommand:
    """Test /files command handler."""

    @pytest.mark.asyncio
    async def test_no_session(self, mock_token_tracker, mock_session_state):
        """Test /files with no active session."""
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_files_command(None, show_all=False)
            mock_console.print.assert_called_once()
            assert "No active sandbox session" in str(mock_console.print.call_args)

    @pytest.mark.asyncio
    async def test_no_sandbox(self, mock_token_tracker, mock_session_state):
        """Test /files with session but no sandbox."""
        session = Mock()
        session.sandbox = None
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_files_command(session, show_all=False)
            mock_console.print.assert_called_once()
            assert "No active sandbox session" in str(mock_console.print.call_args)

    @pytest.mark.asyncio
    async def test_lists_files(self, mock_session):
        """Test /files lists sandbox files."""
        mock_session.sandbox.glob_files.return_value = [
            "/home/daytona/test.py",
            "/home/daytona/src/main.py",
        ]
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_files_command(mock_session, show_all=False)
            # Should print files
            assert mock_console.print.call_count > 1

    @pytest.mark.asyncio
    async def test_filters_excluded_dirs(self, mock_session):
        """Test /files filters system directories."""
        mock_session.sandbox.glob_files.return_value = [
            "/home/daytona/test.py",
            "/home/daytona/code/internal.py",
            "/home/daytona/tools/tool.py",
        ]
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_files_command(mock_session, show_all=False)
            # Should mention files but filter system dirs
            assert mock_console.print.call_count > 0

    @pytest.mark.asyncio
    async def test_show_all_includes_system_dirs(self, mock_session):
        """Test /files all includes system directories."""
        mock_session.sandbox.glob_files.return_value = [
            "/home/daytona/test.py",
            "/home/daytona/code/internal.py",
        ]
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_files_command(mock_session, show_all=True)
            # Should show all files
            assert mock_console.print.call_count > 0


class TestHandleViewCommand:
    """Test /view command handler."""

    @pytest.mark.asyncio
    async def test_missing_path(self):
        """Test /view without path shows usage."""
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_view_command(None, "")
            mock_console.print.assert_called_once()
            assert "Usage" in str(mock_console.print.call_args)

    @pytest.mark.asyncio
    async def test_no_session(self, mock_token_tracker, mock_session_state):
        """Test /view with no active session."""
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_view_command(None, "test.py")
            mock_console.print.assert_called_once()
            assert "No active sandbox session" in str(mock_console.print.call_args)

    @pytest.mark.asyncio
    async def test_file_not_found(self, mock_session):
        """Test /view with non-existent file."""
        mock_session.sandbox.read_file.return_value = None
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_view_command(mock_session, "missing.py")
            # Should print file not found error
            assert any("not found" in str(call).lower() for call in mock_console.print.call_args_list)

    @pytest.mark.asyncio
    async def test_displays_file_content(self, mock_session):
        """Test /view displays file content with syntax highlighting."""
        mock_session.sandbox.read_file.return_value = "def hello():\n    print('world')"
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_view_command(mock_session, "test.py")
            # Should print the content
            assert mock_console.print.call_count > 0

    @pytest.mark.asyncio
    async def test_image_file_downloads(self, mock_session, tmp_path):
        """Test /view downloads image files instead of displaying."""
        mock_session.sandbox.download_file_bytes.return_value = b"fake-image-data"
        with patch("ptc_cli.commands.slash.console") as mock_console, patch("pathlib.Path.cwd", return_value=tmp_path):
            await _handle_view_command(mock_session, "image.png")
            # Should download the image
            assert any("downloaded" in str(call).lower() for call in mock_console.print.call_args_list)


class TestHandleCopyCommand:
    """Test /copy command handler."""

    @pytest.mark.asyncio
    async def test_missing_path(self):
        """Test /copy without path shows usage."""
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_copy_command(None, "")
            mock_console.print.assert_called_once()
            assert "Usage" in str(mock_console.print.call_args)

    @pytest.mark.asyncio
    async def test_no_session(self):
        """Test /copy with no active session."""
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_copy_command(None, "test.py")
            mock_console.print.assert_called_once()
            assert "No active sandbox session" in str(mock_console.print.call_args)

    @pytest.mark.asyncio
    async def test_file_not_found(self, mock_session):
        """Test /copy with non-existent file."""
        mock_session.sandbox.read_file.return_value = None
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_copy_command(mock_session, "missing.py")
            assert any("not found" in str(call).lower() for call in mock_console.print.call_args_list)

    @pytest.mark.asyncio
    async def test_copies_to_clipboard(self, mock_session):
        """Test /copy copies file content to clipboard."""
        mock_session.sandbox.read_file.return_value = "test content"
        with patch("ptc_cli.commands.slash.console") as mock_console:
            # Mock pyperclip module at builtins level
            mock_pyperclip = Mock()
            with patch.dict("sys.modules", {"pyperclip": mock_pyperclip}):
                await _handle_copy_command(mock_session, "test.py")
                mock_pyperclip.copy.assert_called_once_with("test content")
                assert any("copied" in str(call).lower() for call in mock_console.print.call_args_list)

    @pytest.mark.asyncio
    async def test_handles_missing_pyperclip(self, mock_session):
        """Test /copy handles missing pyperclip package."""
        mock_session.sandbox.read_file.return_value = "test content"
        with patch("ptc_cli.commands.slash.console") as mock_console:
            # Simulate ImportError by making import fail
            with patch("builtins.__import__", side_effect=ImportError("No module named 'pyperclip'")):
                await _handle_copy_command(mock_session, "test.py")
                # Should show error about missing package
                assert any("clipboard" in str(call).lower() for call in mock_console.print.call_args_list)


class TestHandleDownloadCommand:
    """Test /download command handler."""

    @pytest.mark.asyncio
    async def test_missing_path(self):
        """Test /download without path shows usage."""
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_download_command(None, "", "")
            mock_console.print.assert_called_once()
            assert "Usage" in str(mock_console.print.call_args)

    @pytest.mark.asyncio
    async def test_no_session(self):
        """Test /download with no active session."""
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_download_command(None, "test.py", "local.py")
            mock_console.print.assert_called_once()
            assert "No active sandbox session" in str(mock_console.print.call_args)

    @pytest.mark.asyncio
    async def test_downloads_text_file(self, mock_session, tmp_path):
        """Test /download saves text file to local filesystem."""
        mock_session.sandbox.read_file.return_value = "test content"
        local_path = tmp_path / "downloaded.py"

        with patch("ptc_cli.commands.slash.console") as mock_console, patch("pathlib.Path.cwd", return_value=tmp_path):
            await _handle_download_command(mock_session, "test.py", str(local_path))
            assert local_path.exists()
            assert local_path.read_text() == "test content"

    @pytest.mark.asyncio
    async def test_downloads_binary_file(self, mock_session, tmp_path):
        """Test /download saves binary file to local filesystem."""
        mock_session.sandbox.download_file_bytes.return_value = b"binary data"
        local_path = tmp_path / "image.png"

        with patch("ptc_cli.commands.slash.console") as mock_console, patch("pathlib.Path.cwd", return_value=tmp_path):
            await _handle_download_command(mock_session, "image.png", str(local_path))
            assert local_path.exists()
            assert local_path.read_bytes() == b"binary data"

    @pytest.mark.asyncio
    async def test_file_not_found(self, mock_session, tmp_path):
        """Test /download handles non-existent file."""
        mock_session.sandbox.read_file.return_value = None
        with patch("ptc_cli.commands.slash.console") as mock_console, patch("pathlib.Path.cwd", return_value=tmp_path):
            await _handle_download_command(mock_session, "missing.py", "local.py")
            assert any("failed" in str(call).lower() for call in mock_console.print.call_args_list)


class TestHandleCommand:
    """Test main command dispatcher."""

    @pytest.mark.asyncio
    async def test_exit_command(self, mock_agent, mock_token_tracker, mock_session_state):
        """Test /exit returns 'exit'."""
        result = await handle_command("/exit", mock_agent, mock_token_tracker, mock_session_state)
        assert result == "exit"

    @pytest.mark.asyncio
    async def test_q_command(self, mock_agent, mock_token_tracker, mock_session_state):
        """Test /q returns 'exit'."""
        result = await handle_command("/q", mock_agent, mock_token_tracker, mock_session_state)
        assert result == "exit"

    @pytest.mark.asyncio
    async def test_help_command(self, mock_agent, mock_token_tracker, mock_session_state):
        """Test /help calls show_help."""
        with patch("ptc_cli.commands.slash.show_help") as mock_show_help:
            result = await handle_command("/help", mock_agent, mock_token_tracker, mock_session_state)
            mock_show_help.assert_called_once()
            assert result == "handled"

    @pytest.mark.asyncio
    async def test_clear_command(self, mock_agent, mock_token_tracker, mock_session_state):
        """Test /clear resets thread_id and clears console."""
        with patch("ptc_cli.commands.slash.console") as mock_console:
            result = await handle_command("/clear", mock_agent, mock_token_tracker, mock_session_state)
            mock_session_state.reset_thread.assert_called_once()
            mock_console.clear.assert_called_once()
            assert result == "handled"

    @pytest.mark.asyncio
    async def test_tokens_command(self, mock_agent, mock_token_tracker, mock_session_state):
        """Test /tokens displays token usage."""
        result = await handle_command("/tokens", mock_agent, mock_token_tracker, mock_session_state)
        mock_token_tracker.display.assert_called_once()
        assert result == "handled"

    @pytest.mark.asyncio
    async def test_files_command(self, mock_agent, mock_token_tracker, mock_session_state, mock_session):
        """Test /files command."""
        with patch("ptc_cli.commands.slash._handle_files_command") as mock_handler:
            result = await handle_command("/files", mock_agent, mock_token_tracker, mock_session_state, mock_session)
            mock_handler.assert_called_once_with(mock_session, show_all=False)
            assert result == "handled"

    @pytest.mark.asyncio
    async def test_files_all_command(self, mock_agent, mock_token_tracker, mock_session_state, mock_session):
        """Test /files all command."""
        with patch("ptc_cli.commands.slash._handle_files_command") as mock_handler:
            result = await handle_command("/files all", mock_agent, mock_token_tracker, mock_session_state, mock_session)
            mock_handler.assert_called_once_with(mock_session, show_all=True)
            assert result == "handled"

    @pytest.mark.asyncio
    async def test_view_command(self, mock_agent, mock_token_tracker, mock_session_state, mock_session):
        """Test /view command."""
        with patch("ptc_cli.commands.slash._handle_view_command") as mock_handler:
            result = await handle_command("/view test.py", mock_agent, mock_token_tracker, mock_session_state, mock_session)
            mock_handler.assert_called_once_with(mock_session, "test.py")
            assert result == "handled"

    @pytest.mark.asyncio
    async def test_copy_command(self, mock_agent, mock_token_tracker, mock_session_state, mock_session):
        """Test /copy command."""
        with patch("ptc_cli.commands.slash._handle_copy_command") as mock_handler:
            result = await handle_command("/copy test.py", mock_agent, mock_token_tracker, mock_session_state, mock_session)
            mock_handler.assert_called_once_with(mock_session, "test.py")
            assert result == "handled"

    @pytest.mark.asyncio
    async def test_download_command(self, mock_agent, mock_token_tracker, mock_session_state, mock_session):
        """Test /download command."""
        with patch("ptc_cli.commands.slash._handle_download_command") as mock_handler:
            result = await handle_command("/download test.py local.py", mock_agent, mock_token_tracker, mock_session_state, mock_session)
            mock_handler.assert_called_once_with(mock_session, "test.py", "local.py")
            assert result == "handled"

    @pytest.mark.asyncio
    async def test_download_command_default_local_path(self, mock_agent, mock_token_tracker, mock_session_state, mock_session):
        """Test /download command with default local path."""
        with patch("ptc_cli.commands.slash._handle_download_command") as mock_handler:
            result = await handle_command("/download test.py", mock_agent, mock_token_tracker, mock_session_state, mock_session)
            mock_handler.assert_called_once_with(mock_session, "test.py", "test.py")
            assert result == "handled"

    @pytest.mark.asyncio
    async def test_unknown_command(self, mock_agent, mock_token_tracker, mock_session_state):
        """Test unknown command shows error."""
        with patch("ptc_cli.commands.slash.console") as mock_console:
            result = await handle_command("/unknown", mock_agent, mock_token_tracker, mock_session_state)
            # Should print unknown command message
            assert any("unknown" in str(call).lower() for call in mock_console.print.call_args_list)
            assert result == "handled"
