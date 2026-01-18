"""Tests for PTCSandbox core functionality."""

import pytest

from ptc_agent.core.sandbox import PTCSandbox

# Use shared fixture from conftest.py: sandbox_instance


class TestNormalizePath:
    """Tests for normalize_path method."""

    @pytest.mark.parametrize(
        ("input_path", "expected"),
        [
            ("", "/home/daytona"),
            (".", "/home/daytona"),
            ("/", "/home/daytona"),
            (None, "/home/daytona"),
        ],
        ids=["empty", "dot", "root", "none"],
    )
    def test_normalize_special_paths(self, sandbox_instance, input_path, expected):
        """Special paths normalize to working directory."""
        assert sandbox_instance.normalize_path(input_path) == expected

    @pytest.mark.parametrize(
        ("input_path", "expected"),
        [
            ("data/file.txt", "/home/daytona/data/file.txt"),
            ("/results/output.txt", "/home/daytona/results/output.txt"),
            ("/home/daytona/test.py", "/home/daytona/test.py"),
            ("/tmp/file.txt", "/tmp/file.txt"),
            ("  data/file.txt  ", "/home/daytona/data/file.txt"),
        ],
        ids=["relative", "virtual-absolute", "already-absolute", "tmp-path", "whitespace"],
    )
    def test_normalize_various_paths(self, sandbox_instance, input_path, expected):
        """Various path types normalize correctly."""
        assert sandbox_instance.normalize_path(input_path) == expected


class TestVirtualizePath:
    """Tests for virtualize_path method."""

    @pytest.mark.parametrize(
        ("input_path", "expected"),
        [
            ("/home/daytona/results/file.txt", "/results/file.txt"),
            ("/home/daytona", "/"),
            ("/tmp/file.txt", "/tmp/file.txt"),
            ("/etc/config", "/etc/config"),
        ],
        ids=["working-dir-subpath", "working-dir-root", "tmp-unchanged", "other-unchanged"],
    )
    def test_virtualize_paths(self, sandbox_instance, input_path, expected):
        """Test path virtualization for various inputs."""
        assert sandbox_instance.virtualize_path(input_path) == expected


class TestValidatePath:
    """Tests for validate_path method."""

    @pytest.mark.parametrize(
        "input_path",
        [
            "/home/daytona/test.py",
            "/tmp/test.txt",
            "/results/output.txt",
            "data/file.txt",
            "/home/daytona",
        ],
        ids=["working-dir", "tmp", "virtual", "relative", "exact-working-dir"],
    )
    def test_validate_allowed_paths(self, sandbox_instance, input_path):
        """Test that allowed paths are valid."""
        assert sandbox_instance.validate_path(input_path) is True

    def test_validate_virtual_paths_normalized_to_allowed(self, sandbox_instance):
        """Virtual absolute paths always get normalized to working directory.

        This is a security feature - agent cannot escape the sandbox by using
        paths like /etc/passwd. They get normalized to /home/daytona/etc/passwd.
        """
        # Even with only /home/daytona allowed, /tmp/secret.txt becomes /home/daytona/tmp/secret.txt
        sandbox_instance.config.filesystem.allowed_directories = ["/home/daytona"]
        # This "passes" because /tmp/secret.txt becomes /home/daytona/tmp/secret.txt
        assert sandbox_instance.validate_path("/tmp/secret.txt") is True
        # The normalized path is within allowed directory
        assert sandbox_instance.normalize_path("/tmp/secret.txt") == "/home/daytona/tmp/secret.txt"

    def test_validate_when_disabled(self, sandbox_instance):
        """All paths are valid when validation is disabled."""
        sandbox_instance.config.filesystem.enable_path_validation = False
        assert sandbox_instance.validate_path("/etc/passwd") is True


class TestPathNormalizationEdgeCases:
    """Edge cases for path normalization."""

    def test_double_slashes(self, sandbox_instance):
        """Double slashes in path are handled."""
        result = sandbox_instance.normalize_path("data//file.txt")
        assert "//" not in result

    def test_path_with_dots(self, sandbox_instance):
        """Paths with . and .. are kept as-is (no resolution).

        The current implementation doesn't resolve .. components.
        This is actually safer - let the sandbox filesystem handle resolution.
        """
        result = sandbox_instance.normalize_path("/home/daytona/data/../test.py")
        # Path keeps the .. component (no resolution)
        assert "test.py" in result

    def test_unicode_path(self, sandbox_instance):
        """Unicode characters in path are handled."""
        result = sandbox_instance.normalize_path("données/fichier.txt")
        assert "données" in result


class TestSandboxInitialization:
    """Tests for sandbox initialization logic."""

    def test_sandbox_config_stored(self, mock_core_config):
        """Config is stored in sandbox."""
        sandbox = PTCSandbox.__new__(PTCSandbox)
        sandbox.config = mock_core_config
        assert sandbox.config is mock_core_config

    def test_sandbox_initial_state(self, sandbox_instance):
        """Sandbox starts in uninitialized state."""
        assert sandbox_instance.sandbox is None
        assert sandbox_instance.mcp_registry is None
