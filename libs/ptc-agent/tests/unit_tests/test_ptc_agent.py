"""Tests for PTCAgent class."""

from unittest.mock import Mock, patch

from ptc_agent.agent import PTCAgent
from ptc_agent.core.mcp_registry import MCPToolInfo

# Use shared fixtures from conftest.py:
# - mock_agent_config: provides a mock agent config with LLM definition
# - mock_agent_config_direct_llm: provides a mock agent config without LLM definition


class TestPTCAgentInit:
    """Tests for PTCAgent initialization."""

    def test_init_with_llm_definition(self, mock_agent_config):
        """Test initialization with file-based LLM config."""
        agent = PTCAgent(mock_agent_config)

        assert agent.config is mock_agent_config
        assert agent.llm is not None
        assert agent.subagents == {}

    def test_init_with_direct_llm(self, mock_agent_config_direct_llm):
        """Test initialization with directly provided LLM."""
        agent = PTCAgent(mock_agent_config_direct_llm)

        assert agent.config is mock_agent_config_direct_llm
        assert agent.llm is not None

    def test_init_stores_config(self, mock_agent_config):
        """Test that config is stored correctly."""
        agent = PTCAgent(mock_agent_config)
        assert agent.config is mock_agent_config


class TestGetSubagentSummary:
    """Tests for _get_subagent_summary method."""

    def test_summary_before_create_agent(self, mock_agent_config):
        """Test subagent summary before create_agent is called."""
        agent = PTCAgent(mock_agent_config)

        summary = agent._get_subagent_summary()
        assert "general-purpose" in summary

    def test_summary_no_subagents(self, mock_agent_config_direct_llm):
        """Test summary when no subagents configured."""
        agent = PTCAgent(mock_agent_config_direct_llm)

        summary = agent._get_subagent_summary()
        assert "No sub-agents configured" in summary

    def test_summary_after_create_agent(self, mock_agent_config):
        """Test summary after subagents are populated."""
        agent = PTCAgent(mock_agent_config)
        # Simulate subagents being populated after create_agent
        agent.subagents = {
            "research": {
                "description": "Research specialist",
                "tools": ["tavily_search", "web_fetch"],
            },
            "general-purpose": {
                "description": "General tasks",
                "tools": ["execute_code"],
            },
        }

        summary = agent._get_subagent_summary()
        assert "research" in summary
        assert "Research specialist" in summary
        assert "general-purpose" in summary


class TestGetToolSummary:
    """Tests for _get_tool_summary method."""

    def test_tool_summary_empty_registry(self, mock_agent_config):
        """Test tool summary with empty registry."""
        agent = PTCAgent(mock_agent_config)

        mock_registry = Mock()
        mock_registry.get_all_tools.return_value = {}

        summary = agent._get_tool_summary(mock_registry)
        # Empty tools should still return something
        assert isinstance(summary, str)

    def test_tool_summary_with_tools(self, mock_agent_config):
        """Test tool summary formats tools correctly."""
        agent = PTCAgent(mock_agent_config)

        # Create mock tools
        mock_tool = MCPToolInfo(
            name="search",
            description="Search the web",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
            server_name="tavily",
        )

        mock_registry = Mock()
        mock_registry.get_all_tools.return_value = {"tavily": [mock_tool]}

        summary = agent._get_tool_summary(mock_registry)
        assert "tavily" in summary.lower() or "search" in summary.lower()


class TestBuildSystemPrompt:
    """Tests for _build_system_prompt method."""

    @patch("ptc_agent.agent.agent.get_loader")
    def test_build_system_prompt_calls_loader(self, mock_get_loader, mock_agent_config):
        """Test that _build_system_prompt uses the template loader."""
        agent = PTCAgent(mock_agent_config)

        mock_loader = Mock()
        mock_loader.get_system_prompt.return_value = "Test prompt"
        mock_get_loader.return_value = mock_loader

        result = agent._build_system_prompt(
            tool_summary="Tools: test",
            subagent_summary="Subagents: test",
        )

        assert result == "Test prompt"
        mock_loader.get_system_prompt.assert_called_once()

    @patch("ptc_agent.agent.agent.get_loader")
    def test_build_system_prompt_passes_arguments(self, mock_get_loader, mock_agent_config):
        """Test that arguments are passed to loader."""
        agent = PTCAgent(mock_agent_config)

        mock_loader = Mock()
        mock_loader.get_system_prompt.return_value = "Prompt"
        mock_get_loader.return_value = mock_loader

        agent._build_system_prompt(
            tool_summary="My tools",
            subagent_summary="My subagents",
        )

        call_kwargs = mock_loader.get_system_prompt.call_args.kwargs
        assert call_kwargs["tool_summary"] == "My tools"
        assert call_kwargs["subagent_summary"] == "My subagents"


class TestPTCAgentEdgeCases:
    """Edge case tests for PTCAgent."""

    def test_multiple_subagents_configured(self, mock_agent_config):
        """Test with multiple subagents configured."""
        mock_agent_config.subagents_enabled = ["research", "general-purpose", "code-review"]
        agent = PTCAgent(mock_agent_config)

        summary = agent._get_subagent_summary()
        assert "research" in summary
        assert "general-purpose" in summary
        assert "code-review" in summary

    def test_llm_without_model_attribute(self, mock_agent_config_direct_llm):
        """Test LLM without standard model attributes."""
        # Remove model attributes
        mock_agent_config_direct_llm.get_llm_client.return_value._llm_type = "custom"
        del mock_agent_config_direct_llm.get_llm_client.return_value.model_name

        # Should still initialize without error
        agent = PTCAgent(mock_agent_config_direct_llm)
        assert agent is not None
