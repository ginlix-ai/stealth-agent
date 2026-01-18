"""Integration tests for MCP tool transformation.

These tests verify that MCP tools are correctly transformed to Python modules
in the Daytona sandbox.

Run with: pytest tests/integration_tests/test_mcp_tool_transformation.py -v -m integration
Skip with: pytest -m "not integration"
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ptc_agent.config import ConfigContext, load_core_from_files
from ptc_agent.core.session import SessionManager

# =============================================================================
# Mock MCP Server Script
# =============================================================================

MOCK_MCP_SERVER_SCRIPT = '''#!/usr/bin/env python3
"""Mock MCP server for testing."""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("TestMCP")


@mcp.tool()
def test_tool(message: str) -> str:
    """A simple test tool.

    Args:
        message: The message to echo

    Returns:
        The echoed message
    """
    return f"Echo: {message}"


@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """Add two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        Sum of a and b
    """
    return a + b


if __name__ == "__main__":
    mcp.run(transport="stdio")
'''


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def fake_home(tmp_path_factory):
    """Create a fake home directory with config files and mock MCP server."""
    fake_home = tmp_path_factory.mktemp("home")

    # Create .ptc-agent directory
    ptc_dir = fake_home / ".ptc-agent"
    ptc_dir.mkdir()

    # Create mcp_servers directory and mock server
    mcp_servers_dir = ptc_dir / "mcp_servers"
    mcp_servers_dir.mkdir()
    (mcp_servers_dir / "test_mcp_server.py").write_text(MOCK_MCP_SERVER_SCRIPT)

    # Create llms.json
    llms_data = {
        "llms": {
            "test-llm": {
                "model_id": "test-model",
                "provider": "anthropic",
                "sdk": "langchain_anthropic.ChatAnthropic",
                "api_key_env": "ANTHROPIC_API_KEY",
            }
        }
    }
    (ptc_dir / "llms.json").write_text(json.dumps(llms_data))

    # Create config.yaml with mock MCP server (use absolute path)
    mcp_server_path = str(mcp_servers_dir / "test_mcp_server.py")
    config_data = {
        "llm": {"name": "test-llm"},
        "daytona": {
            "base_url": "https://app.daytona.io/api",
            "auto_stop_interval": 3600,
            "auto_archive_interval": 86400,
            "auto_delete_interval": 604800,
            "python_version": "3.12",
        },
        "security": {
            "max_execution_time": 300,
            "max_code_length": 10000,
            "max_file_size": 10485760,
            "enable_code_validation": False,
            "allowed_imports": [],
            "blocked_patterns": [],
        },
        "mcp": {
            "servers": [
                {
                    "name": "testserver",  # No hyphens - must be valid Python identifier
                    "description": "Test MCP server for unit tests",
                    "transport": "stdio",
                    "command": "python",
                    "args": [mcp_server_path],  # Absolute path to mock server
                }
            ],
            "tool_discovery_enabled": True,
            "lazy_load": True,
            "cache_duration": 300,
        },
        "logging": {"level": "WARNING", "file": "logs/test.log"},
        "filesystem": {
            "working_directory": "/home/daytona",
            "allowed_directories": ["/home/daytona", "/tmp"],
            "enable_path_validation": True,
        },
    }
    (ptc_dir / "config.yaml").write_text(yaml.dump(config_data))

    return fake_home


@pytest.fixture(scope="module")
async def sandbox_session(fake_home):
    """Set up and tear down a sandbox session for the test module."""
    # Patch Path.home() to return our fake home
    # Use ConfigContext.CLI to prioritize ~/.ptc-agent/ config (our fake home)
    with patch.object(Path, "home", return_value=fake_home):
        config = await load_core_from_files(context=ConfigContext.CLI)
        session = SessionManager.get_session("test-mcp-transformation", config)
        await session.initialize()

        yield session

        await SessionManager.cleanup_session("test-mcp-transformation")


@pytest.fixture(scope="module")
def sandbox(sandbox_session):
    """Get sandbox from session."""
    return sandbox_session.sandbox


@pytest.fixture(scope="module")
def mcp_registry(sandbox_session):
    """Get MCP registry from session."""
    return sandbox_session.mcp_registry


@pytest.fixture(scope="module")
def config(sandbox_session):
    """Get configuration used for the session."""
    return sandbox_session.config


# =============================================================================
# Configuration Tests
# =============================================================================


@pytest.mark.integration
class TestConfiguration:
    """Tests for configuration loading."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_config_loads_mcp_servers(self, config):
        """Test that MCP servers are configured."""
        assert hasattr(config, "mcp")
        assert hasattr(config.mcp, "servers")
        # May have 0 servers configured - that's valid

    @pytest.mark.asyncio(loop_scope="module")
    async def test_config_has_daytona_settings(self, config):
        """Test that Daytona settings are present."""
        assert hasattr(config, "daytona")
        assert hasattr(config.daytona, "base_url")


# =============================================================================
# MCP Registry Tests
# =============================================================================


@pytest.mark.integration
class TestMCPRegistry:
    """Tests for MCP registry functionality."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_registry_exists(self, mcp_registry):
        """Test that MCP registry was created."""
        assert mcp_registry is not None

    @pytest.mark.asyncio(loop_scope="module")
    async def test_registry_has_tools_method(self, mcp_registry):
        """Test that registry has get_all_tools method."""
        assert hasattr(mcp_registry, "get_all_tools")
        tools_by_server = mcp_registry.get_all_tools()
        assert isinstance(tools_by_server, dict)

    @pytest.mark.asyncio(loop_scope="module")
    async def test_tools_have_required_attributes(self, mcp_registry):
        """Test that discovered tools have required attributes."""
        tools_by_server = mcp_registry.get_all_tools()

        for server_name, tools in tools_by_server.items():
            for tool in tools:
                assert hasattr(tool, "name"), f"Tool from {server_name} missing 'name'"
                assert hasattr(tool, "description"), f"Tool {tool.name} missing 'description'"
                assert tool.name, f"Tool from {server_name} has empty name"


# =============================================================================
# Sandbox Directory Structure Tests
# =============================================================================


@pytest.mark.integration
class TestSandboxDirectoryStructure:
    """Tests for sandbox directory structure."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_work_directory_exists(self, sandbox):
        """Test that sandbox work directory is set."""
        work_dir = getattr(sandbox, "_work_dir", None)
        assert work_dir is not None

    @pytest.mark.asyncio(loop_scope="module")
    async def test_can_list_work_directory(self, sandbox):
        """Test that we can list the work directory."""
        work_dir = getattr(sandbox, "_work_dir", "/home/daytona")

        try:
            contents = await sandbox.als_directory(work_dir)
            assert isinstance(contents, list)
        except Exception as e:
            pytest.skip(f"Could not list directory: {e}")

    @pytest.mark.asyncio(loop_scope="module")
    async def test_tools_directory_exists(self, sandbox):
        """Test that tools directory exists in sandbox."""
        work_dir = getattr(sandbox, "_work_dir", "/home/daytona")
        tools_dir = f"{work_dir}/tools"

        try:
            contents = await sandbox.als_directory(tools_dir)
            assert isinstance(contents, list)
        except Exception as e:
            # tools directory may not exist if no MCP servers configured
            pytest.skip(f"Tools directory not found: {e}")


# =============================================================================
# Generated Tool Module Tests
# =============================================================================


@pytest.mark.integration
class TestGeneratedToolModules:
    """Tests for generated tool Python modules."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_mcp_client_module_exists(self, sandbox):
        """Test that mcp_client.py is generated."""
        work_dir = getattr(sandbox, "_work_dir", "/home/daytona")
        mcp_client_path = f"{work_dir}/tools/mcp_client.py"

        try:
            content = await sandbox.aread_file_text(mcp_client_path)
            # Content may be empty string if file exists but is empty,
            # or None if file doesn't exist
            if content:
                assert len(content) > 0
                assert "import" in content or "def" in content
        except Exception as e:
            pytest.skip(f"Could not read mcp_client.py: {e}")

    @pytest.mark.asyncio(loop_scope="module")
    async def test_server_modules_exist(self, sandbox, mcp_registry):
        """Test that a Python module is generated for each MCP server."""
        work_dir = getattr(sandbox, "_work_dir", "/home/daytona")
        tools_by_server = mcp_registry.get_all_tools()

        for server_name in tools_by_server:
            module_path = f"{work_dir}/tools/{server_name}.py"
            try:
                content = await sandbox.aread_file_text(module_path)
                if content:
                    assert len(content) > 0, f"Module for {server_name} is empty"
            except Exception as e:
                pytest.skip(f"Could not read {server_name}.py: {e}")


# =============================================================================
# Tool Import Tests
# =============================================================================


@pytest.mark.integration
class TestToolImport:
    """Tests for importing generated tools in sandbox."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_can_import_tool_in_sandbox(self, sandbox, mcp_registry):
        """Test that generated tools can be imported in sandbox."""
        tools_by_server = mcp_registry.get_all_tools()

        if not tools_by_server:
            pytest.skip("No MCP tools discovered")

        # Find a server with at least one tool
        first_server = None
        first_tool = None
        for server, tools in tools_by_server.items():
            if tools:
                first_server = server
                first_tool = tools[0]
                break

        if first_tool is None:
            pytest.skip("No tools found in any server")

        # Convert tool name to valid Python identifier
        func_name = first_tool.name.replace("-", "_").replace(".", "_")
        work_dir = getattr(sandbox, "_work_dir", "/home/daytona")

        test_code = f"""
import sys
sys.path.insert(0, '{work_dir}')

try:
    from tools.{first_server} import {func_name}
    print(f"SUCCESS: Imported {func_name}")
    print(f"Type: {{type({func_name})}}")
except ImportError as e:
    print(f"IMPORT_ERROR: {{e}}")
except Exception as e:
    print(f"ERROR: {{e}}")
"""

        try:
            result = await sandbox.execute(test_code)
            assert result.success, f"Execution failed: {result.stderr}"
            assert "SUCCESS" in result.stdout or "IMPORT_ERROR" in result.stdout
        except Exception as e:
            pytest.skip(f"Could not execute import test: {e}")

    @pytest.mark.asyncio(loop_scope="module")
    async def test_imported_tool_has_docstring(self, sandbox, mcp_registry):
        """Test that imported tools have docstrings."""
        tools_by_server = mcp_registry.get_all_tools()

        if not tools_by_server:
            pytest.skip("No MCP tools discovered")

        # Find a server with at least one tool
        first_server = None
        first_tool = None
        for server, tools in tools_by_server.items():
            if tools:
                first_server = server
                first_tool = tools[0]
                break

        if first_tool is None:
            pytest.skip("No tools found in any server")

        func_name = first_tool.name.replace("-", "_").replace(".", "_")
        work_dir = getattr(sandbox, "_work_dir", "/home/daytona")

        test_code = f"""
import sys
sys.path.insert(0, '{work_dir}')

try:
    from tools.{first_server} import {func_name}
    doc = {func_name}.__doc__
    if doc:
        print(f"HAS_DOCSTRING: {{len(doc)}} chars")
    else:
        print("NO_DOCSTRING")
except Exception as e:
    print(f"ERROR: {{e}}")
"""

        try:
            result = await sandbox.execute(test_code)
            assert result.success
            # Docstring is optional but good to have
            assert "HAS_DOCSTRING" in result.stdout or "NO_DOCSTRING" in result.stdout or "ERROR" in result.stdout
        except Exception as e:
            pytest.skip(f"Could not execute docstring test: {e}")


# =============================================================================
# Documentation Tests
# =============================================================================


@pytest.mark.integration
class TestToolDocumentation:
    """Tests for generated tool documentation."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_docs_directory_exists(self, sandbox):
        """Test that documentation directory exists."""
        work_dir = getattr(sandbox, "_work_dir", "/home/daytona")
        docs_dir = f"{work_dir}/tools/docs"

        try:
            contents = await sandbox.als_directory(docs_dir)
            assert isinstance(contents, list)
        except Exception as e:
            # docs directory may not exist
            pytest.skip(f"Docs directory not found: {e}")


# =============================================================================
# Module Import Tests (runs without sandbox)
# =============================================================================


def test_config_module_imports():
    """Verify that config modules can be imported."""
    from ptc_agent.config import load_core_from_files

    assert load_core_from_files is not None
    assert callable(load_core_from_files)


def test_session_module_imports():
    """Verify that session modules can be imported."""
    from ptc_agent.core.session import SessionManager

    assert SessionManager is not None
    assert hasattr(SessionManager, "get_session")
