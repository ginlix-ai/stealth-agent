from unittest.mock import AsyncMock, Mock, patch

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from ptc_cli.commands.slash import (
    _handle_copy_command,
    _handle_download_command,
    _handle_files_command,
    _handle_view_command,
    _normalize_path,
    _render_tree,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.workspace_id = "ws-123"

    # Workspace is always running in these tests.
    client.get_workspace = AsyncMock(return_value={"workspace_id": "ws-123", "status": "running"})
    client.start_workspace = AsyncMock(return_value={})

    client.list_workspace_files = AsyncMock(return_value=[])
    client.read_workspace_file = AsyncMock(return_value={"content": ""})
    client.download_workspace_file = AsyncMock(return_value=b"")

    return client


class TestNormalizePath:
    def test_removes_home_prefix(self):
        assert _normalize_path("/home/daytona/test.py") == "test.py"
        assert _normalize_path("/home/daytona/src/main.py") == "src/main.py"

    def test_preserves_other_paths(self):
        assert _normalize_path("/tmp/config") == "/tmp/config"
        assert _normalize_path("relative/path") == "relative/path"
        assert _normalize_path("/results/foo.txt") == "results/foo.txt"


class TestRenderTree:
    def test_single_file(self):
        files = ["test.py"]
        result = _render_tree(files)
        assert any("test.py" in line for line in result)

    def test_nested_files(self):
        files = ["src/main.py", "src/utils.py", "tests/test_main.py"]
        result = _render_tree(files)
        assert any("src" in line for line in result)
        assert any("tests" in line for line in result)
        assert any("main.py" in line for line in result)

    def test_empty_list(self):
        assert _render_tree([]) == []


class TestHandleRefreshCommand:
    @pytest.mark.asyncio
    async def test_refresh_calls_api_and_updates_files(self, mock_client):
        from ptc_cli.commands.slash import handle_command
        from ptc_cli.core.state import SessionState

        token_tracker = Mock()
        session_state = SessionState()
        session_state.sandbox_completer = Mock()
        session_state.sandbox_completer.set_files = Mock()

        mock_client.refresh_workspace = AsyncMock(return_value={"message": "ok"})
        mock_client.list_workspace_files = AsyncMock(return_value=["README.md"])

        with patch("ptc_cli.commands.slash.console"):
            result = await handle_command("/refresh", mock_client, token_tracker, session_state)

        assert result == "handled"
        mock_client.refresh_workspace.assert_awaited_once()
        mock_client.list_workspace_files.assert_awaited()
        assert session_state.sandbox_files == ["README.md"]
        session_state.sandbox_completer.set_files.assert_called_once()


class TestHandleFilesCommand:
    @pytest.mark.asyncio
    async def test_lists_files(self, mock_client):
        mock_client.list_workspace_files = AsyncMock(return_value=["test.py", "src/main.py"])
        with patch("ptc_cli.commands.slash.console") as mock_console:
            files = await _handle_files_command(mock_client, show_all=False)
            assert files
            assert mock_console.print.call_count > 0
        mock_client.list_workspace_files.assert_awaited_once_with(include_system=False)

    @pytest.mark.asyncio
    async def test_show_all_includes_system_dirs(self, mock_client):
        mock_client.list_workspace_files = AsyncMock(return_value=["test.py", "code/internal.py"])
        with patch("ptc_cli.commands.slash.console"):
            await _handle_files_command(mock_client, show_all=True)
        mock_client.list_workspace_files.assert_awaited_once_with(include_system=True)


class TestHandleViewCommand:
    @pytest.mark.asyncio
    async def test_missing_path(self, mock_client):
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_view_command(mock_client, "")
            assert "Usage" in str(mock_console.print.call_args)

    @pytest.mark.asyncio
    async def test_displays_file_content(self, mock_client):
        mock_client.read_workspace_file = AsyncMock(return_value={"content": "def hello():\n    return 1"})
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_view_command(mock_client, "test.py")
            assert mock_console.print.call_count > 0

    @pytest.mark.asyncio
    async def test_binary_file_downloads(self, mock_client, tmp_path, monkeypatch):
        mock_client.download_workspace_file = AsyncMock(return_value=b"fake-image-data")
        monkeypatch.setattr("pathlib.Path.cwd", lambda: tmp_path)
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_view_command(mock_client, "image.png")
            assert any("Downloaded" in str(call) for call in mock_console.print.call_args_list)

    @pytest.mark.asyncio
    async def test_directory_lists_files(self, mock_client):
        mock_client.list_workspace_files = AsyncMock(return_value=["tools/a.py", "tools/b.py"])
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_view_command(mock_client, "tools/")
            assert mock_console.print.call_count > 0
        mock_client.list_workspace_files.assert_awaited_once_with(path="tools/", include_system=True, pattern="*")

    @pytest.mark.asyncio
    async def test_fallback_to_directory_listing_on_404(self, mock_client):
        request = httpx.Request("GET", "http://localhost")
        response = httpx.Response(404, request=request, json={"detail": "File not found"})
        mock_client.read_workspace_file = AsyncMock(side_effect=httpx.HTTPStatusError("not found", request=request, response=response))
        mock_client.list_workspace_files = AsyncMock(return_value=["tools/a.py"])

        with patch("ptc_cli.commands.slash.console"):
            await _handle_view_command(mock_client, "tools")

        mock_client.read_workspace_file.assert_awaited_once_with(path="tools")
        mock_client.list_workspace_files.assert_awaited_once_with(path="tools/", include_system=True, pattern="*")


class TestHandleCopyCommand:
    @pytest.mark.asyncio
    async def test_missing_path(self, mock_client):
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_copy_command(mock_client, "")
            assert "Usage" in str(mock_console.print.call_args)

    @pytest.mark.asyncio
    async def test_copies_to_clipboard(self, mock_client):
        mock_client.read_workspace_file = AsyncMock(return_value={"content": "test content"})
        with patch("ptc_cli.commands.slash.console"), patch.dict("sys.modules", {"pyperclip": Mock()}):
            import pyperclip  # type: ignore

            pyperclip.copy = Mock()
            await _handle_copy_command(mock_client, "test.py")
            pyperclip.copy.assert_called_once_with("test content")

    @pytest.mark.asyncio
    async def test_handles_missing_pyperclip(self, mock_client):
        mock_client.read_workspace_file = AsyncMock(return_value={"content": "test content"})
        with patch("ptc_cli.commands.slash.console") as mock_console:
            with patch("builtins.__import__", side_effect=ImportError("No module named 'pyperclip'")):
                await _handle_copy_command(mock_client, "test.py")
            assert any("Clipboard" in str(call) or "clipboard" in str(call).lower() for call in mock_console.print.call_args_list)


class TestHandleDownloadCommand:
    @pytest.mark.asyncio
    async def test_missing_path(self, mock_client):
        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_download_command(mock_client, "", None)
            assert "Usage" in str(mock_console.print.call_args)

    @pytest.mark.asyncio
    async def test_downloads_file(self, mock_client, tmp_path, monkeypatch):
        mock_client.download_workspace_file = AsyncMock(return_value=b"test content")
        monkeypatch.setattr("pathlib.Path.cwd", lambda: tmp_path)

        local_path = tmp_path / "downloaded.py"
        with patch("ptc_cli.commands.slash.console"):
            await _handle_download_command(mock_client, "test.py", str(local_path))

        assert local_path.exists()
        assert local_path.read_bytes() == b"test content"

    @pytest.mark.asyncio
    async def test_handles_http_error(self, mock_client, tmp_path, monkeypatch):
        request = httpx.Request("GET", "http://localhost")
        response = httpx.Response(403, request=request, json={"detail": "Forbidden"})
        mock_client.download_workspace_file = AsyncMock(
            side_effect=httpx.HTTPStatusError("forbidden", request=request, response=response)
        )
        monkeypatch.setattr("pathlib.Path.cwd", lambda: tmp_path)

        with patch("ptc_cli.commands.slash.console") as mock_console:
            await _handle_download_command(mock_client, "secret.txt", None)

        assert any("Forbidden" in str(call) for call in mock_console.print.call_args_list)
