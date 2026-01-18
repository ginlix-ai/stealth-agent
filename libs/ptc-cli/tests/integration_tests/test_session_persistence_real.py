"""Real API tests for session persistence.

These tests require DAYTONA_API_KEY environment variable to be set.
They test actual sandbox creation and session persistence.
"""

import json
import os

import pytest
import yaml

# Skip all tests if DAYTONA_API_KEY is not set
pytestmark = pytest.mark.skipif(
    not os.environ.get("DAYTONA_API_KEY"),
    reason="DAYTONA_API_KEY not set - skipping real sandbox tests",
)


@pytest.fixture
def fake_home_with_config(tmp_path, monkeypatch):
    """Set up fake home with required config files for testing."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

    # Create .ptc-agent directory with config files
    ptc_dir = fake_home / ".ptc-agent"
    ptc_dir.mkdir()

    # Create minimal llms.json with the LLM referenced in config.yaml
    llms_data = {
        "llms": {
            "claude-sonnet-4-5": {
                "model_id": "claude-sonnet-4-5-20241022",
                "provider": "anthropic",
                "sdk": "langchain_anthropic.ChatAnthropic",
                "api_key_env": "ANTHROPIC_API_KEY",
            }
        }
    }
    (ptc_dir / "llms.json").write_text(json.dumps(llms_data))

    # Create minimal config.yaml with all required fields
    config_data = {
        "llm": {"name": "claude-sonnet-4-5"},
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
            "servers": [],
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


class TestSessionPersistenceReal:
    """Test session persistence with real sandbox."""

    @pytest.mark.asyncio
    async def test_session_persisted_on_create(self, fake_home_with_config):
        """Test that session.json is created after agent creation."""
        from ptc_cli.agent.lifecycle import create_agent_with_session
        from ptc_cli.agent.persistence import load_persisted_session

        agent_name = "test-persist-create"

        agent, session, reusing, _, _ = await create_agent_with_session(
            agent_name=agent_name,
            persist_session=True,
        )

        try:
            # Should not be reusing on first create
            assert reusing is False

            # Check persisted session exists
            persisted = load_persisted_session(agent_name)
            assert persisted is not None
            assert persisted["sandbox_id"] == session.sandbox.sandbox_id
        finally:
            if session:
                await session.stop()

    @pytest.mark.asyncio
    async def test_session_reuse_when_config_unchanged(self, fake_home_with_config):
        """Test that second create reuses sandbox if config unchanged."""
        from ptc_cli.agent.lifecycle import create_agent_with_session
        from ptc_cli.agent.persistence import delete_persisted_session

        agent_name = "test-persist-reuse"

        # First creation
        agent1, session1, reusing1, _, _ = await create_agent_with_session(
            agent_name=agent_name,
            persist_session=True,
        )
        first_sandbox_id = session1.sandbox.sandbox_id

        # Don't stop session1 - we want to reuse it

        # Second creation - should reuse
        agent2, session2, reusing2, _, _ = await create_agent_with_session(
            agent_name=agent_name,
            persist_session=True,
        )

        try:
            assert reusing2 is True
            assert session2.sandbox.sandbox_id == first_sandbox_id
        finally:
            if session2:
                await session2.stop()
            delete_persisted_session(agent_name)
