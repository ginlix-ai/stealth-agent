"""Unit tests for Settings class and configuration functions."""

from pathlib import Path

import pytest


class TestFindProjectRoot:
    """Test _find_project_root function."""

    def test_finds_git_dir_in_current_directory(self, temp_project):
        """Test finding .git directory in current directory."""
        from ptc_cli.core.config import _find_project_root

        result = _find_project_root(temp_project)
        assert result == temp_project

    def test_finds_git_dir_in_parent_directory(self, temp_project):
        """Test finding .git directory in parent directory."""
        from ptc_cli.core.config import _find_project_root

        # Create a subdirectory
        subdir = temp_project / "src" / "components"
        subdir.mkdir(parents=True)

        result = _find_project_root(subdir)
        assert result == temp_project

    def test_returns_none_without_git_directory(self, tmp_path):
        """Test returns None when no .git directory exists."""
        from ptc_cli.core.config import _find_project_root

        # Create a directory without .git
        no_git_dir = tmp_path / "no_git"
        no_git_dir.mkdir()

        result = _find_project_root(no_git_dir)
        assert result is None

    def test_walks_up_multiple_levels(self, temp_project):
        """Test walking up multiple directory levels."""
        from ptc_cli.core.config import _find_project_root

        # Create a deeply nested directory
        deep_dir = temp_project / "a" / "b" / "c" / "d" / "e"
        deep_dir.mkdir(parents=True)

        result = _find_project_root(deep_dir)
        assert result == temp_project

    def test_defaults_to_cwd_when_no_path_provided(self, monkeypatch, temp_project):
        """Test uses current working directory when no path provided."""
        from ptc_cli.core.config import _find_project_root

        monkeypatch.chdir(temp_project)
        result = _find_project_root()
        assert result == temp_project


class TestSettingsFromEnvironment:
    """Test Settings.from_environment class method."""

    def test_detects_daytona_api_key(self, temp_project, monkeypatch):
        """Test detects DAYTONA_API_KEY from environment."""
        from ptc_cli.core.config import Settings

        monkeypatch.setenv("DAYTONA_API_KEY", "test-api-key-123")
        settings = Settings.from_environment(start_path=temp_project)

        assert settings.daytona_api_key == "test-api-key-123"

    def test_no_api_key_returns_none(self, temp_project, monkeypatch):
        """Test returns None when no API key is set."""
        from ptc_cli.core.config import Settings

        monkeypatch.delenv("DAYTONA_API_KEY", raising=False)
        settings = Settings.from_environment(start_path=temp_project)

        assert settings.daytona_api_key is None

    def test_detects_project_root(self, temp_project):
        """Test detects project root from start_path."""
        from ptc_cli.core.config import Settings

        settings = Settings.from_environment(start_path=temp_project)
        assert settings.project_root == temp_project

    def test_no_project_returns_none(self, tmp_path):
        """Test returns None for project_root when not in a git project."""
        from ptc_cli.core.config import Settings

        no_project_dir = tmp_path / "no_project"
        no_project_dir.mkdir()

        settings = Settings.from_environment(start_path=no_project_dir)
        assert settings.project_root is None


class TestSettingsPathMethods:
    """Test Settings path-related methods."""

    def test_user_ptc_agent_dir(self, settings_no_project):
        """Test user_ptc_agent_dir returns correct path."""
        expected = Path.home() / ".ptc-agent"
        assert settings_no_project.user_ptc_agent_dir == expected

    def test_get_agent_dir(self, settings_no_project):
        """Test get_agent_dir returns correct path."""
        expected = Path.home() / ".ptc-agent" / "test-agent"
        assert settings_no_project.get_agent_dir("test-agent") == expected

    def test_get_agent_dir_with_spaces(self, settings_no_project):
        """Test get_agent_dir handles agent names with spaces."""
        expected = Path.home() / ".ptc-agent" / "my test agent"
        assert settings_no_project.get_agent_dir("my test agent") == expected

    def test_get_agent_dir_invalid_name_raises_error(self, settings_no_project):
        """Test get_agent_dir raises ValueError for invalid names."""
        with pytest.raises(ValueError, match="Invalid agent name"):
            settings_no_project.get_agent_dir("../../../etc/passwd")

    def test_get_agent_dir_empty_name_raises_error(self, settings_no_project):
        """Test get_agent_dir raises ValueError for empty names."""
        with pytest.raises(ValueError, match="Invalid agent name"):
            settings_no_project.get_agent_dir("")

    def test_get_session_file_path(self, settings_no_project):
        """Test get_session_file_path returns correct path."""
        expected = Path.home() / ".ptc-agent" / "test-agent" / "session.json"
        assert settings_no_project.get_session_file_path("test-agent") == expected

    def test_ensure_agent_dir_creates_directory(self, temp_home, settings_no_project):
        """Test ensure_agent_dir creates directory structure."""
        agent_dir = settings_no_project.ensure_agent_dir("test-agent")

        assert agent_dir.exists()
        assert agent_dir.is_dir()
        assert agent_dir == temp_home / ".ptc-agent" / "test-agent"

    def test_ensure_agent_dir_idempotent(self, temp_home, settings_no_project):
        """Test ensure_agent_dir can be called multiple times."""
        agent_dir1 = settings_no_project.ensure_agent_dir("test-agent")
        agent_dir2 = settings_no_project.ensure_agent_dir("test-agent")

        assert agent_dir1 == agent_dir2
        assert agent_dir1.exists()

    def test_ensure_agent_dir_invalid_name_raises_error(self, settings_no_project):
        """Test ensure_agent_dir raises ValueError for invalid names."""
        with pytest.raises(ValueError, match="Invalid agent name"):
            settings_no_project.ensure_agent_dir("../../../etc/passwd")


class TestSettingsProperties:
    """Test Settings properties."""

    def test_has_daytona_true(self, settings_with_project):
        """Test has_daytona returns True when API key is set."""
        assert settings_with_project.has_daytona is True

    def test_has_daytona_false(self, settings_no_project, monkeypatch):
        """Test has_daytona returns False when API key is not set."""
        from ptc_cli.core.config import Settings

        monkeypatch.delenv("DAYTONA_API_KEY", raising=False)
        settings = Settings(daytona_api_key=None, project_root=None)

        assert settings.has_daytona is False

    def test_has_project_true(self, settings_with_project):
        """Test has_project returns True when in a project."""
        assert settings_with_project.has_project is True

    def test_has_project_false(self, settings_no_project):
        """Test has_project returns False when not in a project."""
        assert settings_no_project.has_project is False


class TestSettingsProjectAgentMd:
    """Test Settings project agent.md path methods."""

    def test_get_project_agent_md_path_with_project(self, settings_with_project):
        """Test get_project_agent_md_path returns correct path when in project."""
        expected = settings_with_project.project_root / ".ptc-agent" / "agent.md"
        assert settings_with_project.get_project_agent_md_path() == expected

    def test_get_project_agent_md_path_without_project(self, settings_no_project):
        """Test get_project_agent_md_path returns None when not in project."""
        assert settings_no_project.get_project_agent_md_path() is None

    def test_get_user_agent_md_path(self, settings_no_project):
        """Test get_user_agent_md_path returns correct path."""
        expected = Path.home() / ".ptc-agent" / "test-agent" / "agent.md"
        assert settings_no_project.get_user_agent_md_path("test-agent") == expected

    def test_ensure_project_ptc_agent_dir_with_project(self, settings_with_project):
        """Test ensure_project_ptc_agent_dir creates directory in project."""
        result = settings_with_project.ensure_project_ptc_agent_dir()

        assert result is not None
        assert result.exists()
        assert result.is_dir()
        assert result == settings_with_project.project_root / ".ptc-agent"

    def test_ensure_project_ptc_agent_dir_without_project(self, settings_no_project):
        """Test ensure_project_ptc_agent_dir returns None when not in project."""
        result = settings_no_project.ensure_project_ptc_agent_dir()
        assert result is None


class TestSettingsIsValidAgentName:
    """Test Settings._is_valid_agent_name static method."""

    def test_valid_alphanumeric_name(self, settings_no_project):
        """Test valid alphanumeric agent name."""
        assert settings_no_project._is_valid_agent_name("test123")

    def test_valid_name_with_hyphens(self, settings_no_project):
        """Test valid agent name with hyphens."""
        assert settings_no_project._is_valid_agent_name("test-agent")

    def test_valid_name_with_underscores(self, settings_no_project):
        """Test valid agent name with underscores."""
        assert settings_no_project._is_valid_agent_name("test_agent")

    def test_valid_name_with_spaces(self, settings_no_project):
        """Test valid agent name with spaces."""
        assert settings_no_project._is_valid_agent_name("my test agent")

    def test_invalid_name_with_slashes(self, settings_no_project):
        """Test invalid agent name with slashes."""
        assert not settings_no_project._is_valid_agent_name("../../etc/passwd")

    def test_invalid_name_with_special_chars(self, settings_no_project):
        """Test invalid agent name with special characters."""
        assert not settings_no_project._is_valid_agent_name("test@agent")

    def test_invalid_empty_name(self, settings_no_project):
        """Test invalid empty agent name."""
        assert not settings_no_project._is_valid_agent_name("")

    def test_invalid_whitespace_only_name(self, settings_no_project):
        """Test invalid whitespace-only agent name."""
        assert not settings_no_project._is_valid_agent_name("   ")
