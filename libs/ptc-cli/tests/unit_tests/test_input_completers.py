"""Unit tests for input completers."""

from unittest.mock import Mock

from prompt_toolkit.document import Document

from ptc_cli.input.completers import (
    AT_MENTION_RE,
    SLASH_COMMAND_RE,
    SLASH_FILE_CMD_RE,
    CommandCompleter,
    SandboxFileCompleter,
)


class TestSandboxFileCompleter:
    """Test sandbox file completion."""

    def test_set_files(self):
        """Test set_files updates the cached file list."""
        completer = SandboxFileCompleter()
        files = ["test.py", "src/main.py", "README.md"]
        completer.set_files(files)
        assert completer._files == sorted(files)

    def test_at_mention_triggers_completion(self):
        """Test @ mention triggers file completion."""
        completer = SandboxFileCompleter()
        completer.set_files(["test.py", "main.py"])

        doc = Document("Check @te", cursor_position=len("Check @te"))
        event = Mock()

        completions = list(completer.get_completions(doc, event))
        assert len(completions) == 1
        assert completions[0].text == "test.py"

    def test_view_command_triggers_completion(self):
        """Test /view command triggers file completion."""
        completer = SandboxFileCompleter()
        completer.set_files(["test.py", "main.py"])

        doc = Document("/view te", cursor_position=len("/view te"))
        event = Mock()

        completions = list(completer.get_completions(doc, event))
        assert len(completions) == 1
        assert completions[0].text == "test.py"

    def test_copy_command_triggers_completion(self):
        """Test /copy command triggers file completion."""
        completer = SandboxFileCompleter()
        completer.set_files(["test.py", "main.py"])

        doc = Document("/copy te", cursor_position=len("/copy te"))
        event = Mock()

        completions = list(completer.get_completions(doc, event))
        assert len(completions) == 1
        assert completions[0].text == "test.py"

    def test_download_command_triggers_completion(self):
        """Test /download command triggers file completion."""
        completer = SandboxFileCompleter()
        completer.set_files(["test.py", "main.py"])

        doc = Document("/download te", cursor_position=len("/download te"))
        event = Mock()

        completions = list(completer.get_completions(doc, event))
        assert len(completions) == 1
        assert completions[0].text == "test.py"

    def test_partial_path_completion(self):
        """Test partial path completion with substring matching."""
        completer = SandboxFileCompleter()
        completer.set_files(["src/main.py", "src/utils.py", "tests/test_main.py"])

        doc = Document("@src", cursor_position=len("@src"))
        event = Mock()

        completions = list(completer.get_completions(doc, event))
        assert len(completions) == 2  # src/main.py and src/utils.py

    def test_escaped_spaces_in_path(self):
        """Test completion with escaped spaces in path."""
        completer = SandboxFileCompleter()
        completer.set_files(["my file.py", "other.py"])

        doc = Document("@my\\ ", cursor_position=len("@my\\ "))
        event = Mock()

        completions = list(completer.get_completions(doc, event))
        assert len(completions) == 1
        assert "my\\ file.py" in completions[0].text

    def test_filters_system_dirs_for_slash_commands(self):
        """Test system directories are filtered for /view, /copy, /download."""
        completer = SandboxFileCompleter()
        completer.set_files(["test.py", "code/internal.py", "tools/tool.py"])

        doc = Document("/view ", cursor_position=len("/view "))
        event = Mock()

        completions = list(completer.get_completions(doc, event))
        # Should only show test.py, not system dirs
        assert len(completions) == 1
        assert completions[0].text == "test.py"

    def test_no_filter_for_at_mentions(self):
        """Test no filtering for @ mentions (system dirs are allowed)."""
        completer = SandboxFileCompleter()
        completer.set_files(["test.py", "code/internal.py", "tools/tool.py"])

        doc = Document("@", cursor_position=len("@"))
        event = Mock()

        completions = list(completer.get_completions(doc, event))
        # Should show all files including system dirs
        assert len(completions) == 3

    def test_hides_internal_by_default(self):
        completer = SandboxFileCompleter()
        completer.set_files([
            "test.py",
            "_internal/src/data_client/fmp/fmp_client.py",
        ])

        doc = Document("@", cursor_position=len("@"))
        event = Mock()

        completions = list(completer.get_completions(doc, event))
        assert [c.text for c in completions] == ["test.py"]

    def test_allows_internal_when_prefix_typed(self):
        completer = SandboxFileCompleter()
        completer.set_files([
            "test.py",
            "_internal/src/data_client/fmp/fmp_client.py",
        ])

        doc = Document("@_internal/", cursor_position=len("@_internal/"))
        event = Mock()

        completions = list(completer.get_completions(doc, event))
        assert any("_internal/src/data_client/fmp/fmp_client.py" == c.text for c in completions)

    def test_hides_init_pycache_and_pyc(self):
        completer = SandboxFileCompleter()
        completer.set_files([
            "src/__init__.py",
            "src/main.py",
            "src/__pycache__/main.cpython-312.pyc",
        ])

        doc = Document("@", cursor_position=len("@"))
        event = Mock()

        completions = list(completer.get_completions(doc, event))
        assert [c.text for c in completions] == ["src/main.py"]

    def test_no_completion_mid_line(self):
        """Test no completion triggered mid-line without @ or /."""
        completer = SandboxFileCompleter()
        completer.set_files(["test.py", "main.py"])

        doc = Document("some text here", cursor_position=len("some"))
        event = Mock()

        completions = list(completer.get_completions(doc, event))
        assert len(completions) == 0


class TestCommandCompleter:
    """Test command completion."""

    def test_slash_prefix_triggers_completion(self):
        """Test / prefix triggers command completion."""
        completer = CommandCompleter()

        doc = Document("/", cursor_position=1)
        event = Mock()

        completions = list(completer.get_completions(doc, event))
        assert len(completions) > 0
        # All completions should be valid commands
        from ptc_cli.core import COMMANDS

        assert all(c.text in COMMANDS for c in completions)

    def test_partial_command_completion(self):
        """Test partial command completion."""
        completer = CommandCompleter()

        doc = Document("/he", cursor_position=3)
        event = Mock()

        completions = list(completer.get_completions(doc, event))
        assert len(completions) == 1
        assert completions[0].text == "help"

    def test_no_completion_without_slash(self):
        """Test no completion without / prefix."""
        completer = CommandCompleter()

        doc = Document("help", cursor_position=4)
        event = Mock()

        completions = list(completer.get_completions(doc, event))
        assert len(completions) == 0

    def test_no_completion_mid_line(self):
        """Test no completion if / is not at start."""
        completer = CommandCompleter()

        doc = Document("some /help", cursor_position=10)
        event = Mock()

        completions = list(completer.get_completions(doc, event))
        assert len(completions) == 0

    def test_display_meta_shows_description(self):
        """Test completions include command descriptions."""
        completer = CommandCompleter()

        doc = Document("/help", cursor_position=5)
        event = Mock()

        completions = list(completer.get_completions(doc, event))
        assert len(completions) == 1
        assert completions[0].display_meta is not None


class TestRegexPatterns:
    """Test regex patterns used for completion."""

    def test_at_mention_pattern(self):
        """Test @ mention regex pattern."""
        assert AT_MENTION_RE.search("@file.py") is not None
        assert AT_MENTION_RE.search("Check @test.py") is not None
        assert AT_MENTION_RE.search("@src/main.py") is not None
        assert AT_MENTION_RE.search("no mention here") is None

    def test_slash_command_pattern(self):
        """Test slash command regex pattern."""
        assert SLASH_COMMAND_RE.match("/help") is not None
        assert SLASH_COMMAND_RE.match("/") is not None
        assert SLASH_COMMAND_RE.match("/hel") is not None
        assert SLASH_COMMAND_RE.match("help") is None
        assert SLASH_COMMAND_RE.match("text /help") is None

    def test_slash_file_cmd_pattern(self):
        """Test slash file command regex pattern."""
        assert SLASH_FILE_CMD_RE.match("/view test.py") is not None
        assert SLASH_FILE_CMD_RE.match("/copy file.txt") is not None
        assert SLASH_FILE_CMD_RE.match("/download image.png") is not None
        assert SLASH_FILE_CMD_RE.match("/help") is None
        assert SLASH_FILE_CMD_RE.match("/view ") is not None
