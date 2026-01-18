"""Streaming state management for CLI output."""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from rich.markdown import Markdown

if TYPE_CHECKING:
    from rich.console import Console


class StreamingState:
    """Manages streaming output state (spinner, text buffer, response tracking)."""

    def __init__(self, console: "Console", status_message: str, colors: Mapping[str, str]) -> None:
        """Initialize streaming state.

        Args:
            console: Rich console instance for output
            status_message: Initial status message for spinner
            colors: Color configuration dictionary
        """
        self.has_responded = False
        self.pending_text = ""
        self._console = console
        self._colors = colors
        self._status = console.status(status_message, spinner="dots")
        self._status.start()
        self._spinner_active = True

    @property
    def spinner_active(self) -> bool:
        """Check if spinner is currently active.

        Returns:
            True if spinner is active, False otherwise
        """
        return self._spinner_active

    def stop_spinner(self) -> None:
        """Stop the spinner if it's currently active."""
        if self._spinner_active:
            self._status.stop()
            self._spinner_active = False

    def start_spinner(self) -> None:
        """Start the spinner if it's currently inactive."""
        if not self._spinner_active:
            self._status.start()
            self._spinner_active = True

    def update_spinner(self, message: str) -> None:
        """Update the spinner message.

        Args:
            message: New status message to display
        """
        self._status.update(message)

    def flush_text(self, *, final: bool = False) -> None:
        """Flush accumulated text as markdown.

        Args:
            final: If True, flush the pending text as final output
        """
        if not final or not self.pending_text.strip():
            return
        self.stop_spinner()
        if not self.has_responded:
            self._console.print("●", style=self._colors["agent"], markup=False, end=" ")
            self.has_responded = True
        self._console.print(Markdown(self.pending_text.rstrip()), style=self._colors["agent"])
        self.pending_text = ""

    def append_text(self, text: str) -> None:
        """Append text to the pending text buffer.

        Args:
            text: Text to append to the buffer
        """
        self.pending_text += text
