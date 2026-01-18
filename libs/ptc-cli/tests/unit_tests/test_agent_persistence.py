"""Unit tests for session persistence functions."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock


class TestLoadPersistedSession:
    """Test load_persisted_session function."""

    def test_load_valid_session(self, tmp_path, monkeypatch, mock_persisted_session_data):
        """Test loading a valid persisted session."""
        from ptc_cli.agent.persistence import load_persisted_session

        # Create mock settings
        agent_name = "test-agent"
        session_file = tmp_path / ".ptc-agent" / agent_name / "session.json"
        session_file.parent.mkdir(parents=True)
        session_file.write_text(json.dumps(mock_persisted_session_data, indent=2))

        # Mock settings to return our test path
        monkeypatch.setattr(
            "ptc_cli.agent.persistence.settings",
            Mock(get_session_file_path=Mock(return_value=session_file)),
        )

        result = load_persisted_session(agent_name)

        assert result is not None
        assert result["sandbox_id"] == "test-sandbox-456"
        assert result["config_hash"] == "abc12345"
        assert "created_at" in result
        assert "last_used" in result

    def test_load_nonexistent_session(self, tmp_path, monkeypatch):
        """Test loading a session that doesn't exist."""
        from ptc_cli.agent.persistence import load_persisted_session

        # Create a path that doesn't exist
        session_file = tmp_path / "nonexistent" / "session.json"

        monkeypatch.setattr(
            "ptc_cli.agent.persistence.settings",
            Mock(get_session_file_path=Mock(return_value=session_file)),
        )

        result = load_persisted_session("test-agent")
        assert result is None

    def test_load_expired_session(self, tmp_path, monkeypatch):
        """Test loading a session that has expired (>24 hours old)."""
        from ptc_cli.agent.persistence import load_persisted_session

        # Create session data that's 25 hours old
        old_time = datetime.now(tz=UTC) - timedelta(hours=25)
        expired_data = {
            "sandbox_id": "test-sandbox-old",
            "config_hash": "old123",
            "created_at": old_time.isoformat(),
            "last_used": old_time.isoformat(),
        }

        session_file = tmp_path / "session.json"
        session_file.write_text(json.dumps(expired_data, indent=2))

        monkeypatch.setattr(
            "ptc_cli.agent.persistence.settings",
            Mock(get_session_file_path=Mock(return_value=session_file)),
        )

        result = load_persisted_session("test-agent")

        # Should return None and delete the file
        assert result is None
        assert not session_file.exists()

    def test_load_session_missing_required_fields(self, tmp_path, monkeypatch):
        """Test loading a session with missing required fields."""
        from ptc_cli.agent.persistence import load_persisted_session

        # Create session data without required fields
        invalid_data = {
            "created_at": datetime.now(tz=UTC).isoformat(),
            # Missing sandbox_id and config_hash
        }

        session_file = tmp_path / "session.json"
        session_file.write_text(json.dumps(invalid_data, indent=2))

        monkeypatch.setattr(
            "ptc_cli.agent.persistence.settings",
            Mock(get_session_file_path=Mock(return_value=session_file)),
        )

        result = load_persisted_session("test-agent")
        assert result is None

    def test_load_corrupted_json(self, tmp_path, monkeypatch):
        """Test loading a session with corrupted JSON."""
        from ptc_cli.agent.persistence import load_persisted_session

        session_file = tmp_path / "session.json"
        session_file.write_text("{ invalid json content")

        monkeypatch.setattr(
            "ptc_cli.agent.persistence.settings",
            Mock(get_session_file_path=Mock(return_value=session_file)),
        )

        result = load_persisted_session("test-agent")

        # Should return None and delete corrupted file
        assert result is None
        assert not session_file.exists()

    def test_load_session_with_naive_datetime(self, tmp_path, monkeypatch):
        """Test loading a session with naive datetime (old format)."""
        from ptc_cli.agent.persistence import load_persisted_session

        # Create session with naive datetime (no timezone)
        naive_time = datetime.now().replace(tzinfo=None)
        session_data = {
            "sandbox_id": "test-sandbox-naive",
            "config_hash": "naive123",
            "created_at": naive_time.isoformat(),
            "last_used": naive_time.isoformat(),
        }

        session_file = tmp_path / "session.json"
        session_file.write_text(json.dumps(session_data, indent=2))

        monkeypatch.setattr(
            "ptc_cli.agent.persistence.settings",
            Mock(get_session_file_path=Mock(return_value=session_file)),
        )

        result = load_persisted_session("test-agent")

        # Should still load successfully (assumes UTC for naive datetimes)
        assert result is not None
        assert result["sandbox_id"] == "test-sandbox-naive"


class TestSavePersistedSession:
    """Test save_persisted_session function."""

    def test_save_creates_file(self, tmp_path, monkeypatch):
        """Test that save_persisted_session creates a file with correct data."""
        from ptc_cli.agent.persistence import save_persisted_session

        agent_name = "test-agent"
        agent_dir = tmp_path / ".ptc-agent" / agent_name
        session_file = agent_dir / "session.json"

        mock_settings = Mock()
        mock_settings.ensure_agent_dir = Mock(return_value=agent_dir)
        mock_settings.get_session_file_path = Mock(return_value=session_file)

        monkeypatch.setattr("ptc_cli.agent.persistence.settings", mock_settings)

        # Create the directory (simulating ensure_agent_dir)
        agent_dir.mkdir(parents=True)

        # Save session
        save_persisted_session(agent_name, "sandbox-123", "hash-456")

        # Verify file was created
        assert session_file.exists()

        # Verify contents
        data = json.loads(session_file.read_text())
        assert data["sandbox_id"] == "sandbox-123"
        assert data["config_hash"] == "hash-456"
        assert "created_at" in data
        assert "last_used" in data

        # Verify timestamps are recent and timezone-aware
        created_at = datetime.fromisoformat(data["created_at"])
        last_used = datetime.fromisoformat(data["last_used"])
        assert created_at.tzinfo == UTC
        assert last_used.tzinfo == UTC
        assert (datetime.now(tz=UTC) - created_at).total_seconds() < 5

    def test_save_overwrites_existing_file(self, tmp_path, monkeypatch):
        """Test that save_persisted_session overwrites existing file."""
        from ptc_cli.agent.persistence import save_persisted_session

        agent_name = "test-agent"
        agent_dir = tmp_path / ".ptc-agent" / agent_name
        agent_dir.mkdir(parents=True)
        session_file = agent_dir / "session.json"

        # Create existing file
        old_data = {"sandbox_id": "old-sandbox", "config_hash": "old-hash"}
        session_file.write_text(json.dumps(old_data))

        mock_settings = Mock()
        mock_settings.ensure_agent_dir = Mock(return_value=agent_dir)
        mock_settings.get_session_file_path = Mock(return_value=session_file)

        monkeypatch.setattr("ptc_cli.agent.persistence.settings", mock_settings)

        # Save new session
        save_persisted_session(agent_name, "new-sandbox", "new-hash")

        # Verify new data
        data = json.loads(session_file.read_text())
        assert data["sandbox_id"] == "new-sandbox"
        assert data["config_hash"] == "new-hash"


class TestUpdateSessionLastUsed:
    """Test update_session_last_used function."""

    def test_updates_timestamp(self, tmp_path, monkeypatch, mock_persisted_session_data):
        """Test updating the last_used timestamp."""
        from ptc_cli.agent.persistence import update_session_last_used

        session_file = tmp_path / "session.json"

        # Create initial session with old timestamp
        old_time = datetime.now(tz=UTC) - timedelta(hours=2)
        initial_data = mock_persisted_session_data.copy()
        initial_data["last_used"] = old_time.isoformat()
        session_file.write_text(json.dumps(initial_data, indent=2))

        monkeypatch.setattr(
            "ptc_cli.agent.persistence.settings",
            Mock(get_session_file_path=Mock(return_value=session_file)),
        )

        # Update timestamp
        update_session_last_used("test-agent")

        # Verify timestamp was updated
        data = json.loads(session_file.read_text())
        last_used = datetime.fromisoformat(data["last_used"])

        # Should be recent (within last 5 seconds)
        assert (datetime.now(tz=UTC) - last_used).total_seconds() < 5

        # Other fields should remain unchanged
        assert data["sandbox_id"] == mock_persisted_session_data["sandbox_id"]
        assert data["config_hash"] == mock_persisted_session_data["config_hash"]

    def test_update_nonexistent_session(self, tmp_path, monkeypatch):
        """Test updating a nonexistent session does nothing."""
        from ptc_cli.agent.persistence import update_session_last_used

        session_file = tmp_path / "nonexistent.json"

        monkeypatch.setattr(
            "ptc_cli.agent.persistence.settings",
            Mock(get_session_file_path=Mock(return_value=session_file)),
        )

        # Should not raise an error
        update_session_last_used("test-agent")

        # File should still not exist
        assert not session_file.exists()

    def test_update_corrupted_session(self, tmp_path, monkeypatch):
        """Test updating a corrupted session silently fails."""
        from ptc_cli.agent.persistence import update_session_last_used

        session_file = tmp_path / "session.json"
        session_file.write_text("invalid json")

        monkeypatch.setattr(
            "ptc_cli.agent.persistence.settings",
            Mock(get_session_file_path=Mock(return_value=session_file)),
        )

        # Should not raise an error
        update_session_last_used("test-agent")


class TestDeletePersistedSession:
    """Test delete_persisted_session function."""

    def test_deletes_existing_session(self, tmp_path, monkeypatch, mock_persisted_session_data):
        """Test deleting an existing session file."""
        from ptc_cli.agent.persistence import delete_persisted_session

        session_file = tmp_path / "session.json"
        session_file.write_text(json.dumps(mock_persisted_session_data))

        monkeypatch.setattr(
            "ptc_cli.agent.persistence.settings",
            Mock(get_session_file_path=Mock(return_value=session_file)),
        )

        # Verify file exists before deletion
        assert session_file.exists()

        # Delete session
        delete_persisted_session("test-agent")

        # Verify file was deleted
        assert not session_file.exists()

    def test_delete_nonexistent_session(self, tmp_path, monkeypatch):
        """Test deleting a nonexistent session does nothing."""
        from ptc_cli.agent.persistence import delete_persisted_session

        session_file = tmp_path / "nonexistent.json"

        monkeypatch.setattr(
            "ptc_cli.agent.persistence.settings",
            Mock(get_session_file_path=Mock(return_value=session_file)),
        )

        # Should not raise an error
        delete_persisted_session("test-agent")


class TestGetSessionConfigHash:
    """Test get_session_config_hash function."""

    def test_hash_consistency(self, mock_agent_config):
        """Test that the same config produces the same hash."""
        from ptc_cli.agent.persistence import get_session_config_hash

        hash1 = get_session_config_hash(mock_agent_config)
        hash2 = get_session_config_hash(mock_agent_config)

        assert hash1 == hash2
        assert len(hash1) == 8  # Should be 8 characters

    def test_hash_changes_with_config(self, mock_agent_config):
        """Test that different configs produce different hashes."""
        from ptc_cli.agent.persistence import get_session_config_hash

        # Get hash with original config
        hash1 = get_session_config_hash(mock_agent_config)

        # Modify config
        core_config = mock_agent_config.to_core_config()
        core_config.daytona.python_version = "3.12"

        # Get hash with modified config
        hash2 = get_session_config_hash(mock_agent_config)

        # Hashes should be different
        assert hash1 != hash2

    def test_hash_includes_mcp_servers(self):
        """Test that MCP server configuration affects the hash."""
        from ptc_cli.agent.persistence import get_session_config_hash

        # Create config with MCP servers
        config1 = Mock()
        core_config1 = Mock()
        core_config1.daytona = Mock()
        core_config1.daytona.base_url = "https://api.daytona.io"
        core_config1.daytona.python_version = "3.11"
        core_config1.daytona.snapshot_enabled = False
        core_config1.daytona.snapshot_name = None

        # No MCP servers
        core_config1.mcp = Mock()
        core_config1.mcp.servers = []
        config1.to_core_config.return_value = core_config1

        # Create config with different MCP servers
        config2 = Mock()
        core_config2 = Mock()
        core_config2.daytona = Mock()
        core_config2.daytona.base_url = "https://api.daytona.io"
        core_config2.daytona.python_version = "3.11"
        core_config2.daytona.snapshot_enabled = False
        core_config2.daytona.snapshot_name = None

        # With MCP server
        mcp_server = Mock()
        mcp_server.name = "tavily"
        mcp_server.enabled = True
        mcp_server.transport = "stdio"
        mcp_server.command = "npx"
        mcp_server.args = ["-y", "@modelcontextprotocol/server-tavily"]

        core_config2.mcp = Mock()
        core_config2.mcp.servers = [mcp_server]
        config2.to_core_config.return_value = core_config2

        hash1 = get_session_config_hash(config1)
        hash2 = get_session_config_hash(config2)

        # Hashes should be different
        assert hash1 != hash2

    def test_hash_includes_snapshot_config(self):
        """Test that snapshot configuration affects the hash."""
        from ptc_cli.agent.persistence import get_session_config_hash

        # Create config without snapshot
        config1 = Mock()
        core_config1 = Mock()
        core_config1.daytona = Mock()
        core_config1.daytona.base_url = "https://api.daytona.io"
        core_config1.daytona.python_version = "3.11"
        core_config1.daytona.snapshot_enabled = False
        core_config1.daytona.snapshot_name = None
        core_config1.mcp = Mock()
        core_config1.mcp.servers = []
        config1.to_core_config.return_value = core_config1

        # Create config with snapshot
        config2 = Mock()
        core_config2 = Mock()
        core_config2.daytona = Mock()
        core_config2.daytona.base_url = "https://api.daytona.io"
        core_config2.daytona.python_version = "3.11"
        core_config2.daytona.snapshot_enabled = True
        core_config2.daytona.snapshot_name = "my-snapshot"
        core_config2.mcp = Mock()
        core_config2.mcp.servers = []
        config2.to_core_config.return_value = core_config2

        hash1 = get_session_config_hash(config1)
        hash2 = get_session_config_hash(config2)

        # Hashes should be different
        assert hash1 != hash2
