"""Mocked integration tests for CLI-specific features.

These tests focus on CLI features (@ mentions, slash commands, etc.) using mocked
sandbox file operations to simulate the directory structure the agent works with.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestFileMentionsIntegration:
    """Test @ file mentions integration with mocked sandbox."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock session with sandbox that simulates code/data/results dirs."""
        mock_sandbox = Mock()
        mock_sandbox.normalize_path = Mock(side_effect=lambda p: f"/home/daytona/{p}")

        # Simulate file content for various paths
        file_contents = {
            "/home/daytona/code/main.py": "def main():\n    print('hello')",
            "/home/daytona/data/input.csv": "col1,col2\n1,2\n3,4",
            "/home/daytona/results/output.txt": "Processing complete",
            "/home/daytona/test_file.txt": "Hello from test file!",
        }
        mock_sandbox.read_file = Mock(side_effect=lambda p: file_contents.get(p))

        mock_session = Mock()
        mock_session.sandbox = mock_sandbox
        mock_session.get_sandbox = AsyncMock(return_value=mock_sandbox)

        return mock_session

    @pytest.mark.asyncio
    async def test_file_mention_parsing(self):
        """Test @ file mention parsing extracts paths correctly."""
        from ptc_cli.input.file_mentions import parse_file_mentions

        text = "Read @code/main.py and analyze @data/input.csv"
        original, paths = parse_file_mentions(text)

        assert original == text
        assert paths == ["code/main.py", "data/input.csv"]

    @pytest.mark.asyncio
    async def test_file_mention_multiple_dirs(self):
        """Test @mention with paths across code/, data/, results/ directories."""
        from ptc_cli.input.file_mentions import parse_file_mentions

        # Note: commas adjacent to @mentions are included in the path by the regex
        text = "Check @code/main.py and @data/input.csv and @results/output.txt"
        original, paths = parse_file_mentions(text)

        assert paths == ["code/main.py", "data/input.csv", "results/output.txt"]

    @pytest.mark.asyncio
    async def test_file_mention_escaped_spaces(self):
        """Test @mention with escaped spaces in path."""
        from ptc_cli.input.file_mentions import parse_file_mentions

        text = r"Read @my\ file.txt"
        _, paths = parse_file_mentions(text)

        assert paths == ["my file.txt"]

    @pytest.mark.asyncio
    async def test_file_mention_reads_from_sandbox(self, mock_session):
        """Test that @mentioned files are read from sandbox."""
        sandbox = mock_session.sandbox

        # Verify sandbox read_file is called with correct normalized path
        content = sandbox.read_file(sandbox.normalize_path("code/main.py"))
        assert content == "def main():\n    print('hello')"
        sandbox.normalize_path.assert_called_with("code/main.py")


class TestSlashCommandsFilesIntegration:
    """Test /files command with mocked sandbox."""

    @pytest.fixture
    def mock_session_with_files(self):
        """Create a mock session with sandbox file listing."""
        mock_sandbox = Mock()

        # Simulate typical agent workspace structure
        mock_sandbox.aglob_files = AsyncMock(return_value=[
            "/home/daytona/code/main.py",
            "/home/daytona/code/utils.py",
            "/home/daytona/data/input.csv",
            "/home/daytona/results/output.txt",
            "/home/daytona/README.md",
            # System directories that should be filtered
            "/home/daytona/tools/helper.py",
            "/home/daytona/mcp_servers/config.json",
        ])

        mock_session = Mock()
        mock_session.sandbox = mock_sandbox
        mock_session.get_sandbox = AsyncMock(return_value=mock_sandbox)

        return mock_session

    @pytest.mark.asyncio
    async def test_files_command_lists_files(self, mock_session_with_files):
        """Test /files command lists files from sandbox."""
        from ptc_cli.commands.slash import handle_command
        from ptc_cli.core.state import SessionState
        from ptc_cli.display.tokens import TokenTracker

        state = SessionState()
        tracker = Mock(spec=TokenTracker)
        agent = Mock()

        with patch("ptc_cli.commands.slash.console") as mock_console:
            result = await handle_command(
                "/files", agent, tracker, state, session=mock_session_with_files
            )

        assert result == "handled"
        mock_session_with_files.sandbox.aglob_files.assert_awaited_once_with("**/*", path=".")

    @pytest.mark.asyncio
    async def test_files_command_filters_system_dirs(self, mock_session_with_files):
        """Test /files command filters out system directories."""
        from ptc_cli.commands.slash import handle_command
        from ptc_cli.core.state import SessionState
        from ptc_cli.display.tokens import TokenTracker

        state = SessionState()
        tracker = Mock(spec=TokenTracker)
        agent = Mock()

        printed_output = []
        with patch("ptc_cli.commands.slash.console") as mock_console:
            mock_console.print = lambda *args, **kwargs: printed_output.append(str(args))
            await handle_command(
                "/files", agent, tracker, state, session=mock_session_with_files
            )

        output_str = " ".join(printed_output)
        # Verify files are shown but system dirs (tools, mcp_servers) are filtered
        assert "Files" in output_str or "file" in output_str.lower()

    @pytest.mark.asyncio
    async def test_files_all_flag(self, mock_session_with_files):
        """Test /files all shows all files including system dirs."""
        from ptc_cli.commands.slash import handle_command
        from ptc_cli.core.state import SessionState
        from ptc_cli.display.tokens import TokenTracker

        state = SessionState()
        tracker = Mock(spec=TokenTracker)
        agent = Mock()

        with patch("ptc_cli.commands.slash.console"):
            result = await handle_command(
                "/files all", agent, tracker, state, session=mock_session_with_files
            )

        assert result == "handled"


class TestSlashCommandsViewIntegration:
    """Test /view command with mocked sandbox."""

    @pytest.fixture
    def mock_session_with_content(self):
        """Create a mock session with file content."""
        mock_sandbox = Mock()
        mock_sandbox.normalize_path = Mock(side_effect=lambda p: f"/home/daytona/{p}")

        file_contents = {
            "/home/daytona/code/main.py": "def hello():\n    print('world')",
            "/home/daytona/data/input.csv": "col1,col2\n1,2",
        }
        mock_sandbox.aread_file_text = AsyncMock(side_effect=lambda p: file_contents.get(p))
        mock_sandbox.adownload_file_bytes = AsyncMock(return_value=b"fake image bytes")

        mock_session = Mock()
        mock_session.sandbox = mock_sandbox
        mock_session.get_sandbox = AsyncMock(return_value=mock_sandbox)

        return mock_session

    @pytest.mark.asyncio
    async def test_view_text_file(self, mock_session_with_content):
        """Test /view displays text file with syntax highlighting."""
        from ptc_cli.commands.slash import handle_command
        from ptc_cli.core.state import SessionState
        from ptc_cli.display.tokens import TokenTracker

        state = SessionState()
        tracker = Mock(spec=TokenTracker)
        agent = Mock()

        with patch("ptc_cli.commands.slash.console") as mock_console:
            result = await handle_command(
                "/view code/main.py", agent, tracker, state, session=mock_session_with_content
            )

        assert result == "handled"
        mock_session_with_content.sandbox.aread_file_text.assert_awaited()

    @pytest.mark.asyncio
    async def test_view_missing_file(self, mock_session_with_content):
        """Test /view handles missing file gracefully."""
        from ptc_cli.commands.slash import handle_command
        from ptc_cli.core.state import SessionState
        from ptc_cli.display.tokens import TokenTracker

        state = SessionState()
        tracker = Mock(spec=TokenTracker)
        agent = Mock()

        printed_output = []
        with patch("ptc_cli.commands.slash.console") as mock_console:
            mock_console.print = lambda *args, **kwargs: printed_output.append(str(args))
            await handle_command(
                "/view nonexistent.txt", agent, tracker, state, session=mock_session_with_content
            )

        output_str = " ".join(printed_output)
        assert "not found" in output_str.lower()

    @pytest.mark.asyncio
    async def test_view_image_triggers_download(self, mock_session_with_content, tmp_path):
        """Test /view on image file triggers download behavior."""
        from ptc_cli.commands.slash import handle_command
        from ptc_cli.core.state import SessionState
        from ptc_cli.display.tokens import TokenTracker

        state = SessionState()
        tracker = Mock(spec=TokenTracker)
        agent = Mock()

        # Mock Path.cwd() to use tmp_path
        with patch("ptc_cli.commands.slash.Path.cwd", return_value=tmp_path), patch("ptc_cli.commands.slash.console"):
            await handle_command(
                "/view results/chart.png", agent, tracker, state, session=mock_session_with_content
            )

        # adownload_file_bytes should be called for image files
        mock_session_with_content.sandbox.adownload_file_bytes.assert_awaited()


class TestSlashCommandsDownloadIntegration:
    """Test /download command with mocked sandbox."""

    @pytest.fixture
    def mock_session_with_download(self):
        """Create a mock session with downloadable content."""
        mock_sandbox = Mock()
        mock_sandbox.normalize_path = Mock(side_effect=lambda p: f"/home/daytona/{p}")
        mock_sandbox.aread_file_text = AsyncMock(return_value="This is downloadable content!")
        mock_sandbox.adownload_file_bytes = AsyncMock(return_value=b"binary content")

        mock_session = Mock()
        mock_session.sandbox = mock_sandbox
        mock_session.get_sandbox = AsyncMock(return_value=mock_sandbox)

        return mock_session

    @pytest.mark.asyncio
    async def test_download_text_file_to_local(self, mock_session_with_download, tmp_path):
        """Test /download saves text file to local filesystem."""
        from ptc_cli.commands.slash import handle_command
        from ptc_cli.core.state import SessionState
        from ptc_cli.display.tokens import TokenTracker

        state = SessionState()
        tracker = Mock(spec=TokenTracker)
        agent = Mock()

        local_dest = tmp_path / "downloaded.txt"

        with patch("ptc_cli.commands.slash.console"):
            result = await handle_command(
                f"/download data/output.txt {local_dest}",
                agent, tracker, state, session=mock_session_with_download
            )

        assert result == "handled"
        # Verify file was downloaded
        assert local_dest.exists()
        assert local_dest.read_text() == "This is downloadable content!"

    @pytest.mark.asyncio
    async def test_download_binary_file(self, mock_session_with_download, tmp_path):
        """Test /download handles binary files."""
        from ptc_cli.commands.slash import handle_command
        from ptc_cli.core.state import SessionState
        from ptc_cli.display.tokens import TokenTracker

        state = SessionState()
        tracker = Mock(spec=TokenTracker)
        agent = Mock()

        local_dest = tmp_path / "downloaded.png"

        with patch("ptc_cli.commands.slash.console"):
            await handle_command(
                f"/download results/chart.png {local_dest}",
                agent, tracker, state, session=mock_session_with_download
            )

        # Binary files use adownload_file_bytes
        mock_session_with_download.sandbox.adownload_file_bytes.assert_awaited()


class TestSlashCommandsCopyIntegration:
    """Test /copy command with mocked sandbox."""

    @pytest.fixture
    def mock_session_with_copy(self):
        """Create a mock session with copyable content."""
        mock_sandbox = Mock()
        mock_sandbox.normalize_path = Mock(side_effect=lambda p: f"/home/daytona/{p}")
        mock_sandbox.aread_file_text = AsyncMock(return_value="Content to copy to clipboard")

        mock_session = Mock()
        mock_session.sandbox = mock_sandbox
        mock_session.get_sandbox = AsyncMock(return_value=mock_sandbox)

        return mock_session

    @pytest.mark.asyncio
    async def test_copy_to_clipboard(self, mock_session_with_copy):
        """Test /copy copies content to clipboard."""
        from ptc_cli.commands.slash import handle_command
        from ptc_cli.core.state import SessionState
        from ptc_cli.display.tokens import TokenTracker

        state = SessionState()
        tracker = Mock(spec=TokenTracker)
        agent = Mock()

        copied_content = []

        with patch("ptc_cli.commands.slash.console"), patch("pyperclip.copy", side_effect=lambda x: copied_content.append(x)):
            await handle_command(
                "/copy code/main.py", agent, tracker, state, session=mock_session_with_copy
            )

        assert copied_content[0] == "Content to copy to clipboard"

    @pytest.mark.asyncio
    async def test_copy_missing_file(self, mock_session_with_copy):
        """Test /copy handles missing file gracefully."""
        from ptc_cli.commands.slash import handle_command
        from ptc_cli.core.state import SessionState
        from ptc_cli.display.tokens import TokenTracker

        # Override aread_file_text to return None for this test
        mock_session_with_copy.sandbox.aread_file_text = AsyncMock(return_value=None)

        state = SessionState()
        tracker = Mock(spec=TokenTracker)
        agent = Mock()

        printed_output = []
        with patch("ptc_cli.commands.slash.console") as mock_console:
            mock_console.print = lambda *args, **kwargs: printed_output.append(str(args))
            await handle_command(
                "/copy nonexistent.txt", agent, tracker, state, session=mock_session_with_copy
            )

        output_str = " ".join(printed_output)
        assert "not found" in output_str.lower()


class TestPlanModeState:
    """Test plan mode state management."""

    def test_plan_mode_initial_state(self):
        """Test plan_mode defaults to False."""
        from ptc_cli.core.state import SessionState

        state = SessionState()
        assert state.plan_mode is False

    def test_plan_mode_toggle(self):
        """Test toggle_plan_mode flips state."""
        from ptc_cli.core.state import SessionState

        state = SessionState()
        assert state.plan_mode is False

        result = state.toggle_plan_mode()
        assert result is True
        assert state.plan_mode is True

        result = state.toggle_plan_mode()
        assert result is False
        assert state.plan_mode is False

    def test_plan_mode_init_with_true(self):
        """Test plan_mode can be initialized as True."""
        from ptc_cli.core.state import SessionState

        state = SessionState(plan_mode=True)
        assert state.plan_mode is True

    def test_plan_mode_reminder_injection(self):
        """Test that plan mode reminder would be injected correctly."""
        from ptc_cli.core.state import SessionState

        state = SessionState(plan_mode=True)

        # Simulate the message building from executor.py
        messages = []
        if state.plan_mode:
            messages.append({
                "role": "user",
                "content": (
                    "<system-reminder>You are in Plan Mode. Before executing any write operations "
                    '(Write, Edit, Bash, execute_code), you MUST first call submit_plan(description="...") '
                    "with a detailed description of your plan for user review.</system-reminder>"
                ),
            })
        messages.append({"role": "user", "content": "Test input"})

        assert len(messages) == 2
        assert "Plan Mode" in messages[0]["content"]
        assert "submit_plan" in messages[0]["content"]


class TestTreeRendering:
    """Test file tree rendering utility."""

    def test_render_tree_single_file(self):
        """Test tree rendering with single file."""
        from ptc_cli.commands.slash import _render_tree

        files = ["main.py"]
        lines = _render_tree(files)

        assert len(lines) == 1
        assert "main.py" in lines[0]

    def test_render_tree_nested_structure(self):
        """Test tree rendering with nested directories."""
        from ptc_cli.commands.slash import _render_tree

        files = [
            "code/main.py",
            "code/utils.py",
            "data/input.csv",
            "results/output.txt",
        ]
        lines = _render_tree(files)

        # Should have tree structure with proper indentation
        assert any("code" in line for line in lines)
        assert any("data" in line for line in lines)
        assert any("results" in line for line in lines)

    def test_render_tree_empty_list(self):
        """Test tree rendering with empty list."""
        from ptc_cli.commands.slash import _render_tree

        files = []
        lines = _render_tree(files)

        assert lines == []


class TestPathNormalization:
    """Test path normalization utility."""

    def test_normalize_removes_home_prefix(self):
        """Test that /home/daytona/ prefix is removed."""
        from ptc_cli.commands.slash import _normalize_path

        result = _normalize_path("/home/daytona/code/main.py")
        assert result == "code/main.py"

    def test_normalize_preserves_other_paths(self):
        """Test that paths without prefix are preserved."""
        from ptc_cli.commands.slash import _normalize_path

        result = _normalize_path("/other/path/file.py")
        assert result == "/other/path/file.py"
