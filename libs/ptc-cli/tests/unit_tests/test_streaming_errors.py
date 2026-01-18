"""Tests for API error handling from ptc_cli.streaming.errors."""

import pytest

from ptc_cli.streaming.errors import (
    _extract_error_message,
    get_api_error_message,
    is_api_error,
)


class TestIsApiError:
    """Tests for is_api_error function."""

    def test_anthropic_rate_limit_error(self):
        """Test detection of Anthropic RateLimitError."""
        try:
            from anthropic import RateLimitError

            # Create a mock rate limit error
            error = RateLimitError.__new__(RateLimitError)
            error.args = ("rate limit exceeded",)
            assert is_api_error(error) is True
        except ImportError:
            pytest.skip("anthropic SDK not installed")

    def test_anthropic_auth_error(self):
        """Test detection of Anthropic AuthenticationError."""
        try:
            from anthropic import AuthenticationError

            error = AuthenticationError.__new__(AuthenticationError)
            error.args = ("invalid api key",)
            assert is_api_error(error) is True
        except ImportError:
            pytest.skip("anthropic SDK not installed")

    def test_openai_rate_limit_error(self):
        """Test detection of OpenAI RateLimitError."""
        try:
            from openai import RateLimitError

            error = RateLimitError.__new__(RateLimitError)
            error.args = ("rate limit exceeded",)
            assert is_api_error(error) is True
        except ImportError:
            pytest.skip("openai SDK not installed")

    def test_regular_exception_not_api_error(self):
        """Test that regular exceptions are not detected as API errors."""
        assert is_api_error(ValueError("test")) is False
        assert is_api_error(RuntimeError("test")) is False
        assert is_api_error(Exception("test")) is False

    def test_type_error_not_api_error(self):
        """Test that TypeError is not detected as API error."""
        assert is_api_error(TypeError("test")) is False


class TestExtractErrorMessage:
    """Tests for _extract_error_message function."""

    def test_extracts_message_from_json_format(self):
        """Test extraction of message from JSON-like error string."""
        error_str = "Error code: 429 - {'type': 'error', 'error': {'message': 'usage limit exceeded'}}"
        result = _extract_error_message(error_str)
        assert result == "usage limit exceeded"

    def test_truncates_long_messages(self):
        """Test that long messages are truncated."""
        long_message = "x" * 300
        result = _extract_error_message(long_message)
        assert len(result) == 203  # 200 + "..."
        assert result.endswith("...")

    def test_returns_short_messages_unchanged(self):
        """Test that short messages are returned unchanged."""
        short_message = "simple error"
        result = _extract_error_message(short_message)
        assert result == short_message

    def test_handles_empty_string(self):
        """Test handling of empty string."""
        result = _extract_error_message("")
        assert result == ""


class TestGetApiErrorMessage:
    """Tests for get_api_error_message function."""

    def test_rate_limit_error_message_format(self):
        """Test that rate limit errors produce correct message format."""

        # Create a mock exception with RateLimitError in name
        class MockRateLimitError(Exception):
            pass

        MockRateLimitError.__name__ = "RateLimitError"
        error = MockRateLimitError("usage limit exceeded")

        result = get_api_error_message(error)

        assert "[red]Rate limit exceeded[/red]" in result
        assert "usage limit exceeded" in result
        assert "~/.ptc-agent/logs" in result

    def test_auth_error_message_format(self):
        """Test that authentication errors produce correct message format."""

        class MockAuthError(Exception):
            pass

        MockAuthError.__name__ = "AuthenticationError"
        error = MockAuthError("invalid api key")

        result = get_api_error_message(error)

        assert "[red]Authentication failed[/red]" in result
        assert "invalid api key" in result

    def test_connection_error_message_format(self):
        """Test that connection errors produce correct message format."""

        class MockConnectionError(Exception):
            pass

        MockConnectionError.__name__ = "APIConnectionError"
        error = MockConnectionError("connection refused")

        result = get_api_error_message(error)

        assert "[red]Connection failed[/red]" in result
        assert "connection refused" in result

    def test_generic_api_error_message_format(self):
        """Test that generic API errors produce correct message format."""

        class MockAPIError(Exception):
            pass

        MockAPIError.__name__ = "APIError"
        error = MockAPIError("something went wrong")

        result = get_api_error_message(error)

        assert "[red]API error[/red]" in result
        assert "something went wrong" in result

    def test_message_includes_log_path_hint(self):
        """Test that all error messages include log path hint."""
        error = Exception("test error")
        result = get_api_error_message(error)

        assert "~/.ptc-agent/logs" in result
        assert "[dim]" in result  # Check it's dimmed
