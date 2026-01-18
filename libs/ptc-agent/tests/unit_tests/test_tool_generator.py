"""Tests for tool function generator."""

import os
from unittest.mock import patch

from ptc_agent.config.core import MCPServerConfig
from ptc_agent.core.tool_generator import ToolFunctionGenerator


class TestEnvVarResolution:
    """Tests for environment variable resolution in MCP client generation."""

    def test_env_var_resolved_at_generation_time(self):
        """Test that ${VAR} patterns are resolved from host environment."""
        generator = ToolFunctionGenerator()

        server = MCPServerConfig(
            name="test_server",
            transport="stdio",
            command="npx",
            args=["@test/mcp"],
            env={"API_KEY": "${TEST_API_KEY}"},
        )

        with patch.dict(os.environ, {"TEST_API_KEY": "secret-key-12345"}):
            code = generator.generate_mcp_client_code([server])

        # The resolved value should be in the generated code
        assert "secret-key-12345" in code
        # The placeholder should NOT be in the generated code
        assert "${TEST_API_KEY}" not in code

    def test_env_var_missing_keeps_placeholder(self):
        """Test that missing env vars keep the ${VAR} placeholder."""
        generator = ToolFunctionGenerator()

        server = MCPServerConfig(
            name="test_server",
            transport="stdio",
            command="npx",
            args=["@test/mcp"],
            env={"API_KEY": "${NONEXISTENT_VAR_12345}"},
        )

        # Ensure the var doesn't exist
        with patch.dict(os.environ, {}, clear=False):
            if "NONEXISTENT_VAR_12345" in os.environ:
                del os.environ["NONEXISTENT_VAR_12345"]
            code = generator.generate_mcp_client_code([server])

        # The placeholder should remain when var is not set
        assert "${NONEXISTENT_VAR_12345}" in code

    def test_env_var_literal_value_unchanged(self):
        """Test that literal values (without ${}) are passed through unchanged."""
        generator = ToolFunctionGenerator()

        server = MCPServerConfig(
            name="test_server",
            transport="stdio",
            command="npx",
            args=["@test/mcp"],
            env={"MODE": "production", "DEBUG": "false"},
        )

        code = generator.generate_mcp_client_code([server])

        assert '"MODE": "production"' in code
        assert '"DEBUG": "false"' in code

    def test_multiple_env_vars_resolved(self):
        """Test that multiple env vars are all resolved correctly."""
        generator = ToolFunctionGenerator()

        server = MCPServerConfig(
            name="test_server",
            transport="stdio",
            command="npx",
            args=["@test/mcp"],
            env={
                "API_KEY": "${TEST_KEY_1}",
                "SECRET": "${TEST_KEY_2}",
                "MODE": "production",
            },
        )

        with patch.dict(os.environ, {
            "TEST_KEY_1": "key-one",
            "TEST_KEY_2": "key-two",
        }):
            code = generator.generate_mcp_client_code([server])

        assert "key-one" in code
        assert "key-two" in code
        assert "production" in code
        assert "${TEST_KEY_1}" not in code
        assert "${TEST_KEY_2}" not in code

    def test_empty_env_dict(self):
        """Test that empty env dict produces empty dict in code."""
        generator = ToolFunctionGenerator()

        server = MCPServerConfig(
            name="test_server",
            transport="stdio",
            command="npx",
            args=["@test/mcp"],
            env={},
        )

        code = generator.generate_mcp_client_code([server])

        # Should have "env": {} for this server
        assert '"env": {}' in code

    def test_env_var_with_special_characters(self):
        """Test env var values with special characters are handled."""
        generator = ToolFunctionGenerator()

        server = MCPServerConfig(
            name="test_server",
            transport="stdio",
            command="npx",
            args=["@test/mcp"],
            env={"API_KEY": "${TEST_SPECIAL_KEY}"},
        )

        # Test with a value containing special chars
        with patch.dict(os.environ, {"TEST_SPECIAL_KEY": "key-with-dashes_and_underscores"}):
            code = generator.generate_mcp_client_code([server])

        assert "key-with-dashes_and_underscores" in code


class TestMCPClientCodeGeneration:
    """Tests for MCP client code generation structure."""

    def test_stdio_transport_generates_correct_structure(self):
        """Test that stdio transport generates correct server config."""
        generator = ToolFunctionGenerator()

        server = MCPServerConfig(
            name="my_server",
            transport="stdio",
            command="python",
            args=["-m", "my_module"],
            env={"KEY": "value"},
        )

        code = generator.generate_mcp_client_code([server])

        assert '"my_server"' in code
        assert '"transport": "stdio"' in code
        assert '"command": "python"' in code
        assert '"-m"' in code
        assert '"my_module"' in code
        assert '"KEY": "value"' in code

    def test_http_transport_resolves_env_in_url(self):
        """Test that HTTP transport resolves env vars in URL."""
        generator = ToolFunctionGenerator()

        server = MCPServerConfig(
            name="http_server",
            transport="http",
            url="https://api.example.com?key=${HTTP_API_KEY}",
        )

        with patch.dict(os.environ, {"HTTP_API_KEY": "http-secret"}):
            code = generator.generate_mcp_client_code([server])

        assert "http-secret" in code
        assert "${HTTP_API_KEY}" not in code

    def test_sse_transport_resolves_env_in_url(self):
        """Test that SSE transport resolves env vars in URL."""
        generator = ToolFunctionGenerator()

        server = MCPServerConfig(
            name="sse_server",
            transport="sse",
            url="https://sse.example.com?apikey=${SSE_API_KEY}",
        )

        with patch.dict(os.environ, {"SSE_API_KEY": "sse-secret"}):
            code = generator.generate_mcp_client_code([server])

        assert "sse-secret" in code
        assert "${SSE_API_KEY}" not in code
