"""Tests for tool exposure mode comparison (summary vs detailed)."""

import pytest

from ptc_agent.agent.prompts import format_tool_summary
from ptc_agent.core.mcp_registry import MCPToolInfo


@pytest.fixture
def sample_tools():
    """Create sample tools for testing exposure modes."""
    tavily_tools = [
        MCPToolInfo(
            name="tavily_search",
            description="Search the web using Tavily search engine",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Maximum results", "default": 10},
                },
                "required": ["query"],
            },
            server_name="tavily",
        )
    ]

    filesystem_tools = [
        MCPToolInfo(
            name="read_file",
            description="Read contents of a file",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path to read"}},
                "required": ["path"],
            },
            server_name="filesystem",
        ),
        MCPToolInfo(
            name="write_file",
            description="Write content to a file",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
            server_name="filesystem",
        ),
        MCPToolInfo(
            name="list_directory",
            description="List contents of a directory",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Directory path to list"}},
                "required": ["path"],
            },
            server_name="filesystem",
        ),
    ]

    github_tools = [
        MCPToolInfo(
            name="create_issue",
            description="Create a new GitHub issue",
            input_schema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name (owner/repo)"},
                    "title": {"type": "string", "description": "Issue title"},
                    "body": {"type": "string", "description": "Issue body"},
                },
                "required": ["repo", "title"],
            },
            server_name="github",
        ),
        MCPToolInfo(
            name="list_issues",
            description="List issues in a GitHub repository",
            input_schema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name (owner/repo)"},
                    "state": {"type": "string", "description": "Issue state (open, closed, all)", "default": "open"},
                },
                "required": ["repo"],
            },
            server_name="github",
        ),
    ]

    return {
        "tavily": [tool.to_dict() for tool in tavily_tools],
        "filesystem": [tool.to_dict() for tool in filesystem_tools],
        "github": [tool.to_dict() for tool in github_tools],
    }


class TestSummaryMode:
    """Tests for summary mode tool exposure."""

    def test_summary_mode_returns_string(self, sample_tools):
        """Test that summary mode returns a string."""
        result = format_tool_summary(sample_tools, mode="summary")
        assert isinstance(result, str)

    def test_summary_mode_includes_server_names(self, sample_tools):
        """Test that summary mode includes server names."""
        result = format_tool_summary(sample_tools, mode="summary")
        # Should mention at least one server
        assert any(server in result.lower() for server in ["tavily", "filesystem", "github"])


class TestDetailedMode:
    """Tests for detailed mode tool exposure."""

    def test_detailed_mode_returns_string(self, sample_tools):
        """Test that detailed mode returns a string."""
        result = format_tool_summary(sample_tools, mode="detailed")
        assert isinstance(result, str)

    def test_detailed_mode_includes_tool_names(self, sample_tools):
        """Test that detailed mode includes tool names."""
        result = format_tool_summary(sample_tools, mode="detailed")
        # Should include specific tool names
        assert "tavily_search" in result or "read_file" in result or "create_issue" in result

    def test_detailed_mode_includes_parameters(self, sample_tools):
        """Test that detailed mode includes parameter information."""
        result = format_tool_summary(sample_tools, mode="detailed")
        # Should include parameter names like query, path, repo
        assert "query" in result or "path" in result or "repo" in result


class TestModeComparison:
    """Tests comparing summary and detailed modes."""

    def test_both_modes_produce_output(self, sample_tools):
        """Test that both modes produce non-empty output."""
        summary = format_tool_summary(sample_tools, mode="summary")
        detailed = format_tool_summary(sample_tools, mode="detailed")

        assert len(summary) > 0
        assert len(detailed) > 0

    def test_detailed_mode_exposes_full_tool_info_summary_mode_does_not(self, sample_tools):
        """Test that detailed mode exposes MCP tool details while summary mode only shows server info."""
        summary = format_tool_summary(sample_tools, mode="summary")
        detailed = format_tool_summary(sample_tools, mode="detailed")

        # Detailed mode should include actual tool names from MCP
        assert "tavily_search" in detailed
        assert "read_file" in detailed
        assert "write_file" in detailed
        assert "create_issue" in detailed

        # Detailed mode should include parameter names
        assert "query" in detailed  # tavily_search param
        assert "path" in detailed  # read_file param
        assert "repo" in detailed  # create_issue param

        # Summary mode should NOT include individual tool names
        assert "tavily_search" not in summary
        assert "read_file" not in summary
        assert "create_issue" not in summary

        # Summary mode SHOULD include server names
        assert "tavily" in summary
        assert "filesystem" in summary
        assert "github" in summary

        # Summary mode should show tool counts instead
        assert "tools available" in summary or "tool available" in summary


class TestEmptyTools:
    """Tests for edge cases with empty tools."""

    def test_empty_tools_summary_mode(self):
        """Test summary mode with no tools."""
        result = format_tool_summary({}, mode="summary")
        assert isinstance(result, str)

    def test_empty_tools_detailed_mode(self):
        """Test detailed mode with no tools."""
        result = format_tool_summary({}, mode="detailed")
        assert isinstance(result, str)

    def test_single_server_summary(self):
        """Test summary mode with single server."""
        single_tool = {
            "test": [
                {
                    "name": "test_tool",
                    "description": "A test tool",
                    "parameters": {},
                    "return_type": "Any",
                    "server_name": "test",
                }
            ]
        }
        result = format_tool_summary(single_tool, mode="summary")
        assert isinstance(result, str)


class TestModeValidation:
    """Tests for mode parameter validation."""

    def test_invalid_mode_handled(self, sample_tools):
        """Test that invalid mode is handled gracefully."""
        # Should either raise an error or fall back to default
        try:
            result = format_tool_summary(sample_tools, mode="invalid")
            # If it doesn't raise, should still return something
            assert isinstance(result, str)
        except (ValueError, KeyError):
            # Expected behavior for invalid mode
            pass

    def test_default_mode(self, sample_tools):
        """Test that default mode works when not specified."""
        # Call without mode parameter
        result = format_tool_summary(sample_tools)
        assert isinstance(result, str)
        assert len(result) > 0
