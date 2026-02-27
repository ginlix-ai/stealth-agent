"""Completers for sandbox files and commands."""

import re
from collections.abc import Generator

from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
)
from prompt_toolkit.document import Document
from ptc_agent.core.paths import (
    AGENT_SYSTEM_DIRS,
    ALWAYS_HIDDEN_BASENAMES,
    ALWAYS_HIDDEN_PATH_SEGMENTS,
    ALWAYS_HIDDEN_SUFFIXES,
    HIDDEN_DIR_NAMES,
)

from ptc_cli.core import COMMANDS

# Regex patterns for context-aware completion
AT_MENTION_RE = re.compile(r"@(?P<path>(?:[^\s@]|(?<=\\)\s)*)$")
SLASH_COMMAND_RE = re.compile(r"^/(?P<command>[a-z]*)$")
SLASH_FILE_CMD_RE = re.compile(r"^/(view|download|copy)\s+(?P<path>(?:[^\s]|(?<=\\)\s)*)$")

# Derived from shared constants (source of truth: ptc_agent.core.paths)
SYSTEM_DIRS = tuple(f"{d}/" for d in sorted(AGENT_SYSTEM_DIRS))
HIDDEN_DIRS = tuple(f"{d}/" for d in sorted(HIDDEN_DIR_NAMES))
ALWAYS_HIDDEN_SEGMENTS = ALWAYS_HIDDEN_PATH_SEGMENTS


class SandboxFileCompleter(Completer):
    """Activate sandbox file completion for @ mentions and /view, /download, /copy commands.

    Uses a cached file list that is updated after each agent task.
    """

    def __init__(self) -> None:
        """Initialize the sandbox file completer with an empty cache."""
        self._files: list[str] = []  # Cached sandbox file list

    def set_files(self, files: list[str]) -> None:
        """Update the cached file list.

        Always filters out internal cache/bytecode/bootstrap artifacts.

        Args:
            files: List of normalized sandbox file paths
        """
        cleaned: list[str] = []
        for f in files:
            if not f:
                continue
            normalized = f"/{f.lstrip('/')}"
            if normalized.endswith(ALWAYS_HIDDEN_BASENAMES):
                continue
            if normalized.endswith(ALWAYS_HIDDEN_SUFFIXES):
                continue
            if any(seg in normalized for seg in ALWAYS_HIDDEN_SEGMENTS):
                continue
            cleaned.append(f)

        self._files = sorted(cleaned)

    def _complete_path(
        self,
        path_fragment: str,
        *,
        filter_system_dirs: bool = False,
    ) -> Generator[Completion, None, None]:
        """Generate completions for a path fragment using substring matching.

        Args:
            path_fragment: The path fragment to match
            filter_system_dirs: If True, filter out system directories unless
                               user typed an exact prefix (e.g., 'tools/')

        Yields:
            Completion objects for matching paths
        """
        # Unescape the path (user may have typed escaped spaces)
        unescaped_fragment = path_fragment.replace("\\ ", " ")

        # Strip trailing backslash if user is typing an escape
        unescaped_fragment = unescaped_fragment.removesuffix("\\")

        # Check if user typed a system dir prefix (to bypass filtering)
        user_typed_system_prefix = any(
            unescaped_fragment.startswith(d.rstrip("/"))
            for d in SYSTEM_DIRS
        )

        user_typed_hidden_prefix = any(
            unescaped_fragment.startswith(d.rstrip("/"))
            for d in HIDDEN_DIRS
        )

        # Find matching files from cache (substring match for flexibility)
        for file_path in self._files:
            if unescaped_fragment in file_path:
                # Always hide internal directories unless user explicitly typed the prefix.
                if any(file_path.startswith(d) for d in HIDDEN_DIRS) and not user_typed_hidden_prefix:
                    continue

                # Filter system dirs unless user typed exact prefix
                if filter_system_dirs and not user_typed_system_prefix and any(file_path.startswith(d) for d in SYSTEM_DIRS):
                    continue  # Skip system directory files

                # Replace entire typed fragment with full path
                completion_text = file_path.replace(" ", "\\ ")
                yield Completion(
                    text=completion_text,
                    start_position=-len(path_fragment),  # Replace what user typed
                    display=file_path,
                )

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,  # noqa: ARG002
    ) -> Generator[Completion, None, None]:
        """Get sandbox file completions for @ mentions and slash commands.

        Args:
            document: The current document being edited
            complete_event: The completion event (unused)

        Yields:
            Completion objects for matching files
        """
        text = document.text_before_cursor

        # Check for @path pattern (no filtering - user explicitly referencing files)
        m = AT_MENTION_RE.search(text)
        if m:
            yield from self._complete_path(m.group("path"), filter_system_dirs=False)
            return

        # Check for /view, /download, /copy commands (filter system dirs by default)
        m = SLASH_FILE_CMD_RE.match(text)
        if m:
            yield from self._complete_path(m.group("path"), filter_system_dirs=True)


class CommandCompleter(Completer):
    """Activate command completion only when line starts with '/'."""

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,  # noqa: ARG002
    ) -> Generator[Completion, None, None]:
        """Get command completions when / is at the start.

        Args:
            document: The current document being edited
            _complete_event: The completion event (unused)

        Yields:
            Completion objects for matching commands
        """
        text = document.text_before_cursor

        # Use regex to detect /command pattern at start of line
        m = SLASH_COMMAND_RE.match(text)
        if not m:
            return  # Not in a /command context

        command_fragment = m.group("command")

        # Match commands that start with the fragment (case-insensitive)
        for cmd_name, cmd_desc in COMMANDS.items():
            if cmd_name.startswith(command_fragment.lower()):
                yield Completion(
                    text=cmd_name,
                    start_position=-len(command_fragment),  # Fixed position for original document
                    display=cmd_name,
                    display_meta=cmd_desc,
                )
