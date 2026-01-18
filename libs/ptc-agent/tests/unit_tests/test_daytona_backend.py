"""Tests for DaytonaBackend."""

from unittest.mock import AsyncMock, Mock

import pytest

from ptc_agent.agent.backends.daytona import DaytonaBackend


@pytest.fixture
def mock_sandbox():
    """Create a mock sandbox for testing."""
    sandbox = Mock()
    sandbox.config = Mock()
    sandbox.config.filesystem = Mock()
    sandbox.config.filesystem.enable_path_validation = False
    return sandbox


@pytest.mark.asyncio
class TestDaytonaBackendGrepRaw:
    """Tests for DaytonaBackend.agrep_raw() output parsing."""

    async def test_grep_raw_with_string_list_result(self, mock_sandbox):
        mock_sandbox.agrep_content = AsyncMock(
            return_value=[
                "/home/daytona/file1.py:10:def hello():",
                "/home/daytona/file2.py:25:def world():",
            ]
        )

        backend = DaytonaBackend(mock_sandbox)
        result = await backend.agrep_raw("def ", "/")
        assert isinstance(result, list)

        assert len(result) == 2
        assert result[0]["path"] == "/home/daytona/file1.py"
        assert result[0]["line"] == 10
        assert result[0]["text"] == "def hello():"
        assert result[1]["path"] == "/home/daytona/file2.py"
        assert result[1]["line"] == 25
        assert result[1]["text"] == "def world():"

    async def test_grep_raw_with_string_result(self, mock_sandbox):
        mock_sandbox.agrep_content = AsyncMock(return_value="/home/daytona/file.py:5:match line")

        backend = DaytonaBackend(mock_sandbox)
        result = await backend.agrep_raw("match", "/")
        assert isinstance(result, list)

        assert len(result) == 1
        assert result[0]["path"] == "/home/daytona/file.py"
        assert result[0]["line"] == 5
        assert result[0]["text"] == "match line"

    async def test_grep_raw_with_dict_list_result(self, mock_sandbox):
        mock_sandbox.agrep_content = AsyncMock(return_value=[{"path": "/home/daytona/file.py", "line": 10, "text": "match"}])

        backend = DaytonaBackend(mock_sandbox)
        result = await backend.agrep_raw("match", "/")
        assert isinstance(result, list)

        assert len(result) == 1
        assert result[0]["path"] == "/home/daytona/file.py"
        assert result[0]["line"] == 10
        assert result[0]["text"] == "match"

    async def test_grep_raw_with_empty_result(self, mock_sandbox):
        mock_sandbox.agrep_content = AsyncMock(return_value=[])

        backend = DaytonaBackend(mock_sandbox)
        result = await backend.agrep_raw("nomatch", "/")
        assert isinstance(result, list)

        assert result == []

    async def test_grep_raw_with_invalid_line_number(self, mock_sandbox):
        mock_sandbox.agrep_content = AsyncMock(return_value=["/home/daytona/file.py:notanumber:some text"])

        backend = DaytonaBackend(mock_sandbox)
        result = await backend.agrep_raw("text", "/")
        assert isinstance(result, list)

        assert len(result) == 1
        assert result[0]["path"] == "/home/daytona/file.py"
        assert result[0]["line"] == 0
        assert result[0]["text"] == "notanumber:some text"

    async def test_grep_raw_with_colons_in_content(self, mock_sandbox):
        mock_sandbox.agrep_content = AsyncMock(return_value=["/home/daytona/file.py:15:url = 'http://example.com:8080'"])

        backend = DaytonaBackend(mock_sandbox)
        result = await backend.agrep_raw("url", "/")
        assert isinstance(result, list)

        assert len(result) == 1
        assert result[0]["path"] == "/home/daytona/file.py"
        assert result[0]["line"] == 15
        assert result[0]["text"] == "url = 'http://example.com:8080'"

    async def test_grep_raw_with_empty_string_in_list(self, mock_sandbox):
        mock_sandbox.agrep_content = AsyncMock(
            return_value=[
                "/home/daytona/file.py:10:match",
                "",
                "/home/daytona/file2.py:20:another",
            ]
        )

        backend = DaytonaBackend(mock_sandbox)
        result = await backend.agrep_raw("match", "/")
        assert isinstance(result, list)

        assert len(result) == 2
