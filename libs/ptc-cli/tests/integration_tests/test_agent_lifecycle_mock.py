"""Simplified integration tests for agent lifecycle."""

from unittest.mock import Mock

import pytest


class TestAgentLifecyclePersistence:
    """Tests for agent lifecycle persistence functions."""

    def test_session_persistence_functions_exist(self):
        """Test that persistence functions are properly imported."""
        from ptc_cli.agent.persistence import (
            delete_persisted_session,
            get_session_config_hash,
            load_persisted_session,
            save_persisted_session,
            update_session_last_used,
        )

        # Functions should be callable
        assert callable(load_persisted_session)
        assert callable(save_persisted_session)
        assert callable(update_session_last_used)
        assert callable(delete_persisted_session)
        assert callable(get_session_config_hash)

    def test_get_session_config_hash(self):
        """Test get_session_config_hash generates consistent hash."""
        from ptc_cli.agent.persistence import get_session_config_hash

        # Create mock config
        mock_core_config = Mock()
        mock_core_config.daytona = Mock()
        mock_core_config.daytona.base_url = "http://localhost:3000"
        mock_core_config.daytona.python_version = "3.12"
        mock_core_config.daytona.snapshot_enabled = False
        mock_core_config.daytona.snapshot_name = None
        mock_core_config.mcp = Mock()
        mock_core_config.mcp.servers = []

        mock_config = Mock()
        mock_config.to_core_config = Mock(return_value=mock_core_config)

        # Generate hash
        hash1 = get_session_config_hash(mock_config)

        # Should be 8-character hex string
        assert isinstance(hash1, str)
        assert len(hash1) == 8
        assert all(c in "0123456789abcdef" for c in hash1)

        # Should be consistent
        hash2 = get_session_config_hash(mock_config)
        assert hash1 == hash2

    def test_get_session_config_hash_changes_with_config(self):
        """Test hash changes when config changes."""
        from ptc_cli.agent.persistence import get_session_config_hash

        # Create first config
        mock_core_config1 = Mock()
        mock_core_config1.daytona = Mock()
        mock_core_config1.daytona.base_url = "http://localhost:3000"
        mock_core_config1.daytona.python_version = "3.12"
        mock_core_config1.daytona.snapshot_enabled = False
        mock_core_config1.daytona.snapshot_name = None
        mock_core_config1.mcp = Mock()
        mock_core_config1.mcp.servers = []

        mock_config1 = Mock()
        mock_config1.to_core_config = Mock(return_value=mock_core_config1)

        # Create second config with different Python version
        mock_core_config2 = Mock()
        mock_core_config2.daytona = Mock()
        mock_core_config2.daytona.base_url = "http://localhost:3000"
        mock_core_config2.daytona.python_version = "3.11"  # Different!
        mock_core_config2.daytona.snapshot_enabled = False
        mock_core_config2.daytona.snapshot_name = None
        mock_core_config2.mcp = Mock()
        mock_core_config2.mcp.servers = []

        mock_config2 = Mock()
        mock_config2.to_core_config = Mock(return_value=mock_core_config2)

        # Hashes should be different
        hash1 = get_session_config_hash(mock_config1)
        hash2 = get_session_config_hash(mock_config2)

        assert hash1 != hash2


class TestAgentLifecycleImports:
    """Test that lifecycle module imports work correctly."""

    def test_create_agent_with_session_import(self):
        """Test create_agent_with_session can be imported."""
        from ptc_cli.agent.lifecycle import create_agent_with_session

        assert callable(create_agent_with_session)

    @pytest.mark.asyncio
    async def test_create_agent_signature(self):
        """Test create_agent_with_session has correct signature."""
        from inspect import signature

        from ptc_cli.agent.lifecycle import create_agent_with_session

        sig = signature(create_agent_with_session)
        params = list(sig.parameters.keys())

        assert "agent_name" in params
        assert "sandbox_id" in params
        assert "persist_session" in params
        assert "on_progress" in params
