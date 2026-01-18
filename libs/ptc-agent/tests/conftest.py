"""Pytest configuration and shared fixtures for test suite."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ptc_agent.core.mcp_registry import MCPRegistry, MCPToolInfo

# =============================================================================
# Shared Configuration Fixtures
# =============================================================================


@pytest.fixture
def mock_core_config():
    """Create a mock CoreConfig for sandbox testing.

    Use this for tests that need filesystem/daytona/mcp configuration.
    """
    config = Mock()
    config.filesystem = Mock()
    config.filesystem.working_directory = "/home/daytona"
    config.filesystem.allowed_directories = ["/home/daytona", "/tmp"]
    config.filesystem.enable_path_validation = True
    config.daytona = Mock()
    config.daytona.api_key = "test-key"
    config.daytona.base_url = "https://api.daytona.io"
    config.mcp = Mock()
    config.mcp.servers = []
    config.mcp.tool_exposure_mode = "summary"
    return config


@pytest.fixture
def mock_agent_config():
    """Create a mock AgentConfig for agent testing.

    Use this for tests that need LLM client configuration.
    """
    config = Mock()

    # Mock LLM client
    mock_llm = MagicMock()
    mock_llm._llm_type = "openai"
    mock_llm.model = "gpt-4"
    config.get_llm_client.return_value = mock_llm

    # Mock LLM definition (file-based loading)
    config.llm_definition = Mock()
    config.llm_definition.provider = "openai"
    config.llm_definition.model_id = "gpt-4"

    # Mock MCP config
    config.mcp = Mock()
    config.mcp.tool_exposure_mode = "summary"
    config.mcp.servers = []

    # Mock subagents config
    config.subagents_enabled = ["general-purpose"]

    return config


@pytest.fixture
def mock_agent_config_direct_llm():
    """Create a mock AgentConfig with direct LLM (no llm_definition).

    Use this for tests that simulate direct LLM client initialization.
    """
    config = Mock()

    # Mock LLM client with attributes
    mock_llm = MagicMock()
    mock_llm._llm_type = "anthropic"
    mock_llm.model_name = "claude-sonnet-4-20250514"
    config.get_llm_client.return_value = mock_llm

    # No LLM definition (direct create() path)
    config.llm_definition = None

    # Mock MCP config
    config.mcp = Mock()
    config.mcp.tool_exposure_mode = "summary"
    config.mcp.servers = []

    # Mock subagents config
    config.subagents_enabled = []

    return config


# =============================================================================
# Sandbox Fixtures
# =============================================================================


@pytest.fixture
def mock_sandbox(mock_core_config):
    """Create a mock sandbox for tool testing.

    This fixture provides a minimal mock sandbox with common methods stubbed.
    Individual tests should override specific method behaviors as needed.
    """
    sandbox = Mock()
    sandbox.config = mock_core_config
    sandbox.sandbox = None
    sandbox.mcp_registry = None
    sandbox.tool_generator = None
    sandbox._work_dir = "/home/daytona"

    # Path operations
    sandbox.normalize_path = Mock(side_effect=lambda x: x if x else "/home/daytona")
    sandbox.virtualize_path = Mock(side_effect=lambda x: x.replace("/home/daytona", "") or "/")
    sandbox.validate_path = Mock(return_value=True)

    # File operations (sync methods - called via asyncio.to_thread())
    sandbox.read_file = Mock(return_value="")
    sandbox.read_file_range = Mock(return_value="")
    sandbox.write_file = Mock(return_value=True)
    sandbox.edit_file = Mock(return_value={"success": True, "changed": True, "message": "OK"})

    # Search operations
    sandbox.glob_files = Mock(return_value=[])
    sandbox.search_files = Mock(return_value=[])
    sandbox.grep_content = Mock(return_value=[])
    sandbox.list_directory = Mock(return_value=[])

    return sandbox


@pytest.fixture
def sandbox_instance(mock_core_config):
    """Create a real PTCSandbox instance (without async init).

    Use this for testing sandbox methods directly without mocking.
    Note: This bypasses async initialization.
    """
    from ptc_agent.core.sandbox import PTCSandbox

    sandbox = PTCSandbox.__new__(PTCSandbox)
    sandbox.config = mock_core_config
    sandbox.sandbox = None
    sandbox.mcp_registry = None
    sandbox.tool_generator = None
    sandbox._work_dir = "/home/daytona"
    return sandbox


# =============================================================================
# MCP Registry Fixtures
# =============================================================================


@pytest.fixture
def mock_mcp_registry() -> MCPRegistry:
    """Create a mock MCP registry with sample tools.

    Includes tools from tavily and filesystem servers for testing.
    """
    registry = Mock(spec=MCPRegistry)

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
    ]

    registry.get_all_tools.return_value = {
        "tavily": tavily_tools,
        "filesystem": filesystem_tools,
    }

    return registry


@pytest.fixture
def sample_mcp_tool_info():
    """Create a sample MCPToolInfo for testing."""
    return MCPToolInfo(
        name="test_tool",
        description="A test tool for unit tests",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query parameter"},
                "limit": {"type": "integer", "description": "Limit results", "default": 10},
            },
            "required": ["query"],
        },
        server_name="test_server",
    )


# =============================================================================
# Async Fixtures
# =============================================================================


@pytest.fixture
def mock_async_sandbox(mock_sandbox):
    """Create a mock sandbox with async method support.

    Extends mock_sandbox with AsyncMock for async methods.
    """
    from unittest.mock import AsyncMock

    sandbox = mock_sandbox
    sandbox.execute_bash_command = AsyncMock(
        return_value={"success": True, "stdout": "", "stderr": "", "exit_code": 0}
    )
    return sandbox
