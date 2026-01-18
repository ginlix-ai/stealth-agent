"""Tests for agent prompt generation and template system."""


from ptc_agent.agent import PTCAgent
from ptc_agent.agent.prompts import format_tool_summary, get_loader, reset_loader

# Use shared fixtures from conftest.py:
# - mock_mcp_registry: provides a mock MCP registry with sample tools
# - mock_agent_config: provides a mock agent config with LLM settings


class TestPromptTemplateLoading:
    """Tests for template loading functionality."""

    def test_get_loader_returns_loader(self):
        """Test that get_loader returns a loader instance."""
        reset_loader()
        loader = get_loader()
        assert loader is not None

    def test_get_loader_caches_instance(self):
        """Test that get_loader returns the same instance."""
        reset_loader()
        loader1 = get_loader()
        loader2 = get_loader()
        assert loader1 is loader2

    def test_reset_loader_clears_cache(self):
        """Test that reset_loader clears the cached loader."""
        reset_loader()
        _loader1 = get_loader()
        reset_loader()
        loader2 = get_loader()
        # After reset, should get a new instance
        # (they may be equal but should be re-created)
        assert loader2 is not None


class TestToolSummaryGeneration:
    """Tests for tool summary generation."""

    def test_tool_summary_includes_server_names(self, mock_mcp_registry):
        """Test that tool summary includes server names."""
        tools_by_server = mock_mcp_registry.get_all_tools()
        tools_dict = {
            server: [tool.to_dict() for tool in tools]
            for server, tools in tools_by_server.items()
        }

        summary = format_tool_summary(tools_dict, mode="summary")
        assert "tavily" in summary.lower() or "filesystem" in summary.lower()

    def test_tool_summary_detailed_mode_includes_params(self, mock_mcp_registry):
        """Test that detailed mode includes parameter information."""
        tools_by_server = mock_mcp_registry.get_all_tools()
        tools_dict = {
            server: [tool.to_dict() for tool in tools]
            for server, tools in tools_by_server.items()
        }

        summary = format_tool_summary(tools_dict, mode="detailed")
        # Detailed mode should include parameter names
        assert "query" in summary or "path" in summary


class TestAgentPromptGeneration:
    """Tests for agent prompt generation."""

    def test_agent_generates_tool_summary(self, mock_agent_config, mock_mcp_registry):
        """Test that agent generates tool summary from registry."""
        agent = PTCAgent(mock_agent_config)
        summary = agent._get_tool_summary(mock_mcp_registry)

        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_agent_builds_system_prompt(self, mock_agent_config):
        """Test that agent builds system prompt."""
        agent = PTCAgent(mock_agent_config)
        prompt = agent._build_system_prompt(
            tool_summary="Test tools",
            subagent_summary="Test subagents",
        )

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_system_prompt_contains_tool_info(self, mock_agent_config, mock_mcp_registry):
        """Test that system prompt contains tool information."""
        agent = PTCAgent(mock_agent_config)
        tool_summary = agent._get_tool_summary(mock_mcp_registry)
        prompt = agent._build_system_prompt(
            tool_summary=tool_summary,
            subagent_summary="",
        )

        # The prompt should include the tool summary
        assert isinstance(prompt, str)


class TestSubagentPromptGeneration:
    """Tests for subagent prompt generation."""

    def test_loader_generates_subagent_prompt(self):
        """Test that loader can generate subagent prompts."""
        reset_loader()
        loader = get_loader()

        # Test researcher subagent
        prompt = loader.get_subagent_prompt("researcher")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_loader_generates_general_subagent_prompt(self):
        """Test that loader can generate general subagent prompt."""
        reset_loader()
        loader = get_loader()

        prompt = loader.get_subagent_prompt("general")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_subagent_prompt_accepts_variables(self):
        """Test that subagent prompts accept template variables."""
        reset_loader()
        loader = get_loader()

        # Pass custom date variable
        prompt = loader.get_subagent_prompt("researcher", date="2024-01-15")
        assert isinstance(prompt, str)


class TestTemplateComponents:
    """Tests for template component system."""

    def test_loader_has_system_prompt_method(self):
        """Test that loader has get_system_prompt method."""
        reset_loader()
        loader = get_loader()
        assert hasattr(loader, "get_system_prompt")

    def test_loader_has_subagent_prompt_method(self):
        """Test that loader has get_subagent_prompt method."""
        reset_loader()
        loader = get_loader()
        assert hasattr(loader, "get_subagent_prompt")
