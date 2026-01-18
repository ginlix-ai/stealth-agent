"""Tests for StreamingState from ptc_cli.streaming.state."""

from unittest.mock import Mock

import pytest

from ptc_cli.streaming.state import StreamingState


@pytest.fixture
def mock_console():
    """Create a mock Rich console."""
    console = Mock()
    mock_status = Mock()
    console.status.return_value = mock_status
    return console


@pytest.fixture
def colors():
    """Color configuration for testing."""
    return {
        "agent": "#10b981",
        "user": "#ffffff",
        "tool": "#fbbf24",
    }


class TestStreamingState:
    """Tests for StreamingState class."""

    def test_initial_state_values(self, mock_console, colors):
        """Test initial state values."""
        state = StreamingState(mock_console, "Processing...", colors)

        assert state.has_responded is False
        assert state.pending_text == ""
        assert state.spinner_active is True
        assert state._console is mock_console
        assert state._colors == colors

        # Verify spinner was started
        mock_console.status.assert_called_once_with("Processing...", spinner="dots")
        state._status.start.assert_called_once()

    def test_stop_spinner(self, mock_console, colors):
        """Test stop_spinner."""
        state = StreamingState(mock_console, "Processing...", colors)

        state.stop_spinner()

        assert state.spinner_active is False
        state._status.stop.assert_called_once()

    def test_stop_spinner_is_idempotent(self, mock_console, colors):
        """Test stop_spinner is idempotent."""
        state = StreamingState(mock_console, "Processing...", colors)

        state.stop_spinner()
        assert state.spinner_active is False

        # Call again - should not call stop() again
        state._status.reset_mock()
        state.stop_spinner()

        assert state.spinner_active is False
        state._status.stop.assert_not_called()

    def test_start_spinner(self, mock_console, colors):
        """Test start_spinner."""
        state = StreamingState(mock_console, "Processing...", colors)

        # First stop it
        state.stop_spinner()
        assert state.spinner_active is False

        # Reset mock to clear stop() call
        state._status.reset_mock()

        # Start again
        state.start_spinner()

        assert state.spinner_active is True
        state._status.start.assert_called_once()

    def test_start_spinner_when_already_active(self, mock_console, colors):
        """Test start_spinner when already active."""
        state = StreamingState(mock_console, "Processing...", colors)

        # Already active from initialization
        assert state.spinner_active is True

        # Reset mock to clear initialization start() call
        state._status.reset_mock()

        # Try to start again - should not call start()
        state.start_spinner()

        assert state.spinner_active is True
        state._status.start.assert_not_called()

    def test_update_spinner_message(self, mock_console, colors):
        """Test update_spinner message."""
        state = StreamingState(mock_console, "Processing...", colors)

        state.update_spinner("New message")

        state._status.update.assert_called_once_with("New message")

    def test_append_text(self, mock_console, colors):
        """Test append_text."""
        state = StreamingState(mock_console, "Processing...", colors)

        assert state.pending_text == ""

        state.append_text("Hello ")
        assert state.pending_text == "Hello "

        state.append_text("World")
        assert state.pending_text == "Hello World"

    def test_flush_text_with_final_false_does_nothing(self, mock_console, colors):
        """Test flush_text with final=False does nothing."""
        state = StreamingState(mock_console, "Processing...", colors)

        state.append_text("Some text")
        state.flush_text(final=False)

        # Text should still be in buffer
        assert state.pending_text == "Some text"
        # Console print should not be called
        mock_console.print.assert_not_called()

    def test_flush_text_with_empty_text(self, mock_console, colors):
        """Test flush_text with empty text."""
        state = StreamingState(mock_console, "Processing...", colors)

        assert state.pending_text == ""
        state.flush_text(final=True)

        # Should not print anything
        mock_console.print.assert_not_called()

    def test_flush_text_with_final_true_outputs_text_and_clears_buffer(self, mock_console, colors):
        """Test flush_text with final=True outputs text and clears buffer."""
        state = StreamingState(mock_console, "Processing...", colors)

        state.append_text("Hello World")
        state.flush_text(final=True)

        # Spinner should be stopped
        assert state.spinner_active is False

        # Should print the bullet and markdown content
        assert mock_console.print.call_count == 2

        # First call: print bullet
        first_call = mock_console.print.call_args_list[0]
        assert first_call[0][0] == "●"
        assert first_call[1]["style"] == colors["agent"]
        assert first_call[1]["markup"] is False
        assert first_call[1]["end"] == " "

        # Second call: print markdown content
        second_call = mock_console.print.call_args_list[1]
        # First argument should be a Markdown object
        from rich.markdown import Markdown
        assert isinstance(second_call[0][0], Markdown)

        # Buffer should be cleared
        assert state.pending_text == ""

        # has_responded should be True
        assert state.has_responded is True

    def test_flush_text_multiple_times_only_prints_bullet_once(self, mock_console, colors):
        """Test multiple flush_text calls only print bullet once."""
        state = StreamingState(mock_console, "Processing...", colors)

        state.append_text("First message")
        state.flush_text(final=True)

        assert state.has_responded is True
        # Should have printed bullet + content
        assert mock_console.print.call_count == 2

        # Reset mock
        mock_console.reset_mock()

        # Second flush
        state.append_text("Second message")
        state.flush_text(final=True)

        # Should only print content, not bullet
        assert mock_console.print.call_count == 1

    def test_flush_text_with_whitespace_only(self, mock_console, colors):
        """Test flush_text with whitespace-only text."""
        state = StreamingState(mock_console, "Processing...", colors)

        state.append_text("   \n\t  ")
        state.flush_text(final=True)

        # Should not print (whitespace-only is considered empty)
        mock_console.print.assert_not_called()

    def test_spinner_active_property(self, mock_console, colors):
        """Test spinner_active property."""
        state = StreamingState(mock_console, "Processing...", colors)

        assert state.spinner_active is True

        state.stop_spinner()
        assert state.spinner_active is False

        state.start_spinner()
        assert state.spinner_active is True
