"""Tests for filesystem tools."""

from unittest.mock import AsyncMock, Mock

import pytest

from ptc_agent.agent.tools.file_ops import create_filesystem_tools

# Use mock_sandbox from conftest.py - provides a pre-configured mock sandbox


class TestReadFileTool:
    """Tests for read_file tool."""

    @pytest.mark.asyncio
    async def test_read_file_success(self, mock_sandbox):
        """Test successful file read."""
        mock_sandbox.validate_path = Mock(return_value=True)
        mock_sandbox.aread_file_text = AsyncMock(return_value="Hello, world!")

        read_file, _, _ = create_filesystem_tools(mock_sandbox)
        result = await read_file.ainvoke({"file_path": "test.txt"})

        # Result is in cat -n format with line numbers
        assert "Hello, world!" in result
        assert "ERROR" not in result

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, mock_sandbox):
        """Test reading non-existent file."""
        mock_sandbox.validate_path = Mock(return_value=True)
        mock_sandbox.aread_file_text = AsyncMock(return_value=None)

        read_file, _, _ = create_filesystem_tools(mock_sandbox)
        result = await read_file.ainvoke({"file_path": "missing.txt"})

        assert "ERROR" in result
        assert "File not found" in result

    @pytest.mark.asyncio
    async def test_read_file_access_denied(self, mock_sandbox):
        """Test reading file outside allowed directories."""
        mock_sandbox.validate_path = Mock(return_value=False)

        read_file, _, _ = create_filesystem_tools(mock_sandbox)
        result = await read_file.ainvoke({"file_path": "/etc/passwd"})

        assert "ERROR" in result
        assert "Access denied" in result


class TestWriteFileTool:
    """Tests for write_file tool."""

    @pytest.mark.asyncio
    async def test_write_file_success(self, mock_sandbox):
        """Test successful file write."""
        mock_sandbox.validate_path = Mock(return_value=True)
        mock_sandbox.awrite_file_text = AsyncMock(return_value=True)
        mock_sandbox.virtualize_path = Mock(return_value="output.txt")

        _, write_file, _ = create_filesystem_tools(mock_sandbox)
        result = await write_file.ainvoke({
            "file_path": "output.txt",
            "content": "Test content"
        })

        # Result format: "Wrote X bytes to path"
        assert "Wrote 12 bytes" in result
        assert "ERROR" not in result

    @pytest.mark.asyncio
    async def test_write_file_failure(self, mock_sandbox):
        """Test failed file write."""
        mock_sandbox.validate_path = Mock(return_value=True)
        mock_sandbox.awrite_file_text = AsyncMock(return_value=False)

        _, write_file, _ = create_filesystem_tools(mock_sandbox)
        result = await write_file.ainvoke({
            "file_path": "output.txt",
            "content": "Test"
        })

        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_write_file_access_denied(self, mock_sandbox):
        """Test writing file outside allowed directories."""
        mock_sandbox.validate_path = Mock(return_value=False)

        _, write_file, _ = create_filesystem_tools(mock_sandbox)
        result = await write_file.ainvoke({
            "file_path": "/etc/test.txt",
            "content": "Test"
        })

        assert "ERROR" in result
        assert "Access denied" in result


class TestEditFileTool:
    """Tests for edit_file tool."""

    @pytest.mark.asyncio
    async def test_edit_file_success(self, mock_sandbox):
        """Test successful file edit."""
        mock_sandbox.validate_path = Mock(return_value=True)
        mock_sandbox.aedit_file_text = AsyncMock(
            return_value={
                "success": True,
                "changed": True,
                "message": "Successfully edited test.txt",
            }
        )

        _, _, edit_file = create_filesystem_tools(mock_sandbox)
        result = await edit_file.ainvoke({
            "file_path": "test.txt",
            "old_string": "old",
            "new_string": "new"
        })

        # Result returns the message from edit_file
        assert "Successfully edited" in result
        assert "ERROR" not in result

    @pytest.mark.asyncio
    async def test_edit_file_access_denied(self, mock_sandbox):
        """Test editing file outside allowed directories."""
        mock_sandbox.validate_path = Mock(return_value=False)

        _, _, edit_file = create_filesystem_tools(mock_sandbox)
        result = await edit_file.ainvoke({
            "file_path": "/etc/test.txt",
            "old_string": "old",
            "new_string": "new"
        })

        assert "ERROR" in result
        assert "Access denied" in result
