"""Tests for MCP registry and tool info."""


from ptc_agent.core.mcp_registry import MCPToolInfo


class TestMCPToolInfo:
    """Tests for MCPToolInfo class."""

    def test_init_basic(self):
        """Test basic initialization."""
        tool = MCPToolInfo(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {}},
            server_name="test_server",
        )
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.server_name == "test_server"

    def test_get_parameters_empty(self):
        """Test get_parameters with no properties."""
        tool = MCPToolInfo(
            name="test",
            description="Test",
            input_schema={"type": "object"},
            server_name="server",
        )
        params = tool.get_parameters()
        assert params == {}

    def test_get_parameters_with_properties(self):
        """Test get_parameters extracts parameter info correctly."""
        tool = MCPToolInfo(
            name="search",
            description="Search for items",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
            server_name="search_server",
        )
        params = tool.get_parameters()

        assert "query" in params
        assert params["query"]["type"] == "string"
        assert params["query"]["required"] is True
        assert params["query"]["description"] == "Search query"

        assert "limit" in params
        assert params["limit"]["type"] == "integer"
        assert params["limit"]["required"] is False
        assert params["limit"]["default"] == 10

    def test_get_parameters_missing_type(self):
        """Test get_parameters handles missing type gracefully."""
        tool = MCPToolInfo(
            name="test",
            description="Test",
            input_schema={
                "type": "object",
                "properties": {
                    "param": {"description": "No type specified"},
                },
            },
            server_name="server",
        )
        params = tool.get_parameters()
        assert params["param"]["type"] == "any"

    def test_extract_return_type_dict(self):
        """Test return type extraction for dict."""
        tool = MCPToolInfo(
            name="test",
            description="Get data.\n\nReturns:\n    dict with results",
            input_schema={},
            server_name="server",
        )
        assert tool._extract_return_type_from_description() == "dict"

    def test_extract_return_type_list(self):
        """Test return type extraction for list."""
        tool = MCPToolInfo(
            name="test",
            description="Get items.\n\nReturns: list of items",
            input_schema={},
            server_name="server",
        )
        assert tool._extract_return_type_from_description() == "list"

    def test_extract_return_type_string(self):
        """Test return type extraction for string."""
        tool = MCPToolInfo(
            name="test",
            description="Get name.\n\nReturns: string",
            input_schema={},
            server_name="server",
        )
        assert tool._extract_return_type_from_description() == "str"

    def test_extract_return_type_no_returns_section(self):
        """Test return type defaults to Any when no Returns section."""
        tool = MCPToolInfo(
            name="test",
            description="Just a description without returns.",
            input_schema={},
            server_name="server",
        )
        assert tool._extract_return_type_from_description() == "Any"

    def test_extract_return_type_empty_description(self):
        """Test return type defaults to Any for empty description."""
        tool = MCPToolInfo(
            name="test",
            description="",
            input_schema={},
            server_name="server",
        )
        assert tool._extract_return_type_from_description() == "Any"

    def test_to_dict(self):
        """Test to_dict serialization."""
        tool = MCPToolInfo(
            name="test_tool",
            description="A test tool",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
            },
            server_name="test_server",
        )
        result = tool.to_dict()

        assert result["name"] == "test_tool"
        assert result["description"] == "A test tool"
        assert result["server_name"] == "test_server"
        assert "parameters" in result
        assert "return_type" in result


class TestMCPToolInfoEdgeCases:
    """Edge case tests for MCPToolInfo."""

    def test_special_characters_in_name(self):
        """Test tool names with special characters."""
        tool = MCPToolInfo(
            name="get-user_data.v2",
            description="Get user data",
            input_schema={},
            server_name="server",
        )
        assert tool.name == "get-user_data.v2"

    def test_complex_nested_schema(self):
        """Test handling of complex nested schemas."""
        tool = MCPToolInfo(
            name="complex",
            description="Complex tool",
            input_schema={
                "type": "object",
                "properties": {
                    "nested": {
                        "type": "object",
                        "properties": {
                            "inner": {"type": "string"},
                        },
                    },
                    "array": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            server_name="server",
        )
        params = tool.get_parameters()
        assert "nested" in params
        assert params["nested"]["type"] == "object"
        assert "array" in params
        assert params["array"]["type"] == "array"

    def test_unicode_in_description(self):
        """Test unicode characters in description."""
        tool = MCPToolInfo(
            name="test",
            description="Search für Bücher 📚",
            input_schema={},
            server_name="server",
        )
        assert "Bücher" in tool.description
        assert "📚" in tool.description
