"""Unit tests for token tracking."""

from unittest.mock import patch

from ptc_cli.display.tokens import TokenTracker


class TestTokenTracker:
    """Test token tracking functionality."""

    def test_initial_values_are_zero(self):
        """Test initial token counts are zero."""
        tracker = TokenTracker()
        assert tracker.input_tokens == 0
        assert tracker.output_tokens == 0
        assert tracker.baseline_tokens == 0
        assert tracker.total == 0

    def test_set_baseline(self):
        """Test setting baseline token count."""
        tracker = TokenTracker()
        tracker.set_baseline(1000)
        assert tracker.baseline_tokens == 1000

    def test_add_tokens(self):
        """Test adding token counts."""
        tracker = TokenTracker()
        tracker.add(100, 50)
        assert tracker.input_tokens == 100
        assert tracker.output_tokens == 50
        assert tracker.total == 150

    def test_add_takes_maximum_values(self):
        """Test add takes maximum of current and new values."""
        tracker = TokenTracker()
        tracker.add(100, 50)
        tracker.add(80, 60)  # Lower input, higher output

        # Should keep max values
        assert tracker.input_tokens == 100  # max(100, 80)
        assert tracker.output_tokens == 60   # max(50, 60)
        assert tracker.total == 160

    def test_total_property(self):
        """Test total property calculates sum correctly."""
        tracker = TokenTracker()
        tracker.add(250, 150)
        assert tracker.total == 400

    def test_display_method(self):
        """Test display method prints table."""
        tracker = TokenTracker()
        tracker.add(100, 50)
        tracker.set_baseline(500)

        with patch("ptc_cli.display.tokens.console") as mock_console:
            tracker.display()
            # Should print table and newlines
            assert mock_console.print.call_count >= 2

    def test_display_without_baseline(self):
        """Test display method without baseline."""
        tracker = TokenTracker()
        tracker.add(100, 50)

        with patch("ptc_cli.display.tokens.console") as mock_console:
            tracker.display()
            # Should still print table
            assert mock_console.print.call_count >= 2

    def test_display_with_zero_tokens(self):
        """Test display method with zero tokens."""
        tracker = TokenTracker()

        with patch("ptc_cli.display.tokens.console") as mock_console:
            tracker.display()
            # Should print table even with zeros
            assert mock_console.print.call_count >= 2

    def test_multiple_add_operations(self):
        """Test multiple add operations maintain maximum."""
        tracker = TokenTracker()
        tracker.add(50, 25)
        tracker.add(100, 30)
        tracker.add(75, 40)
        tracker.add(120, 20)

        # Should have maximum values
        assert tracker.input_tokens == 120
        assert tracker.output_tokens == 40
        assert tracker.total == 160

    def test_baseline_does_not_affect_total(self):
        """Test baseline is separate from total calculation."""
        tracker = TokenTracker()
        tracker.set_baseline(1000)
        tracker.add(100, 50)

        # Total should be input + output, not including baseline
        assert tracker.total == 150
        assert tracker.baseline_tokens == 1000

    def test_add_with_zero_values(self):
        """Test adding zero values."""
        tracker = TokenTracker()
        tracker.add(100, 50)
        tracker.add(0, 0)

        # Should keep previous values (max)
        assert tracker.input_tokens == 100
        assert tracker.output_tokens == 50

    def test_set_baseline_multiple_times(self):
        """Test setting baseline multiple times."""
        tracker = TokenTracker()
        tracker.set_baseline(500)
        assert tracker.baseline_tokens == 500

        tracker.set_baseline(1000)
        assert tracker.baseline_tokens == 1000

    def test_negative_values_handled(self):
        """Test negative values are handled (edge case)."""
        tracker = TokenTracker()
        tracker.add(100, 50)
        tracker.add(-10, -20)  # Negative values

        # Should keep positive values (max)
        assert tracker.input_tokens == 100
        assert tracker.output_tokens == 50
