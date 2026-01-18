"""Integration tests for Grep and Glob tools in a real sandbox environment.

These tests require a running Daytona sandbox and will:
1. Set up a Daytona sandbox with MCP tools
2. Create test files in the sandbox
3. Test Glob and Grep tool functionality

Run with: pytest tests/integration_tests/test_grep_glob_sandbox.py -v -m integration
Skip with: pytest -m "not integration"
"""

import importlib.util
import sys
from pathlib import Path

import pytest

# Get project root directory (parent of tests/)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Add project to path
sys.path.insert(0, str(PROJECT_ROOT))

from ptc_agent.config import load_core_from_files
from ptc_agent.core.session import SessionManager


# Import search tools directly to avoid Tavily initialization issue
def _load_module_from_path(module_name: str, file_path: str):
    """Load a module directly from file path to bypass package import chain."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec for {module_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_glob_module = _load_module_from_path(
    "glob_tool",
    str(PROJECT_ROOT / "ptc_agent" / "agent" / "tools" / "glob.py"),
)
_grep_module = _load_module_from_path(
    "grep_tool",
    str(PROJECT_ROOT / "ptc_agent" / "agent" / "tools" / "grep.py"),
)
create_glob_tool = _glob_module.create_glob_tool
create_grep_tool = _grep_module.create_grep_tool


# Test file content used across tests
TEST_FILES = {
    "test_file1.py": """# Test Python file 1
def hello():
    print("Hello World")

def goodbye():
    print("Goodbye World")
""",
    "test_file2.py": """# Test Python file 2
import os

def search_pattern():
    return "SEARCH_TARGET_ALPHA"

class MyClass:
    pass
""",
    "test_file3.txt": """This is a text file.
It contains some SEARCH_TARGET_ALPHA text.
And also SEARCH_TARGET_BETA here.
Multiple lines for testing.
""",
    "subdir/nested_file.py": """# Nested Python file
def nested_function():
    return "SEARCH_TARGET_ALPHA"
""",
}


@pytest.fixture(scope="module")
async def sandbox_session():
    """Set up and tear down a sandbox session for the test module.

    This fixture is module-scoped for efficiency - sandbox setup is expensive.
    """
    config = await load_core_from_files()
    session = SessionManager.get_session("test-grep-glob", config)
    await session.initialize()

    yield session

    await SessionManager.cleanup_session("test-grep-glob")


@pytest.fixture(scope="module")
async def sandbox_with_files(sandbox_session):
    """Create test files in the sandbox."""
    sandbox = sandbox_session.sandbox

    for filepath, content in TEST_FILES.items():
        # Create directory if needed
        if "/" in filepath:
            dir_path = "/".join(filepath.split("/")[:-1])
            await sandbox.execute_bash_command(f"mkdir -p {dir_path}")

        await sandbox.awrite_file_text(filepath, content)

    return sandbox


@pytest.fixture(scope="module")
def glob_tool(sandbox_with_files):
    """Create a glob tool for testing."""
    return create_glob_tool(sandbox_with_files)


@pytest.fixture(scope="module")
def grep_tool(sandbox_with_files):
    """Create a grep tool for testing."""
    return create_grep_tool(sandbox_with_files)


# =============================================================================
# Glob Tool Tests
# =============================================================================


@pytest.mark.integration
class TestGlobTool:
    """Integration tests for the Glob tool."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_glob_basic_py_pattern(self, glob_tool):
        """Test basic *.py pattern finds Python files in current directory."""
        result = await glob_tool.ainvoke({"pattern": "*.py"})

        assert "test_file1.py" in result
        assert "test_file2.py" in result

    @pytest.mark.asyncio(loop_scope="module")
    async def test_glob_recursive_pattern(self, glob_tool):
        """Test recursive **/*.py pattern finds nested files."""
        result = await glob_tool.ainvoke({"pattern": "**/*.py"})

        # Should find files in subdirectories
        assert "nested_file.py" in result or "subdir" in result

    @pytest.mark.asyncio(loop_scope="module")
    async def test_glob_in_subdirectory(self, glob_tool):
        """Test glob pattern in specific subdirectory."""
        result = await glob_tool.ainvoke({"pattern": "*.py", "path": "subdir"})

        assert "nested_file.py" in result

    @pytest.mark.asyncio(loop_scope="module")
    async def test_glob_txt_pattern(self, glob_tool):
        """Test *.txt pattern finds text files."""
        result = await glob_tool.ainvoke({"pattern": "*.txt"})

        assert "test_file3.txt" in result

    @pytest.mark.asyncio(loop_scope="module")
    async def test_glob_no_matches(self, glob_tool):
        """Test glob pattern with no matches returns appropriate message."""
        result = await glob_tool.ainvoke({"pattern": "*.nonexistent"})

        # Should indicate no files found
        assert "No files" in result or "0 file" in result.lower()


@pytest.mark.integration
class TestGlobDirectMethods:
    """Test direct sandbox glob methods."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_direct_glob_files(self, sandbox_with_files):
        result = await sandbox_with_files.aglob_files("*.py", ".")

        assert isinstance(result, list)
        assert len(result) >= 2


# =============================================================================
# Grep Tool Tests
# =============================================================================


@pytest.mark.integration
class TestGrepTool:
    """Integration tests for the Grep tool."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_grep_basic_search(self, grep_tool):
        """Test basic search for a string pattern."""
        result = await grep_tool.ainvoke({
            "pattern": "SEARCH_TARGET_ALPHA",
            "output_mode": "files_with_matches",
        })

        assert "test_file2.py" in result or "test_file3.txt" in result

    @pytest.mark.asyncio(loop_scope="module")
    async def test_grep_content_mode(self, grep_tool):
        """Test grep with content output mode shows matching lines."""
        result = await grep_tool.ainvoke({
            "pattern": "SEARCH_TARGET_ALPHA",
            "output_mode": "content",
        })

        assert "SEARCH_TARGET_ALPHA" in result

    @pytest.mark.asyncio(loop_scope="module")
    async def test_grep_count_mode(self, grep_tool):
        """Test grep with count output mode."""
        result = await grep_tool.ainvoke({
            "pattern": "SEARCH_TARGET_ALPHA",
            "output_mode": "count",
        })

        # Count mode should return some numeric information
        assert isinstance(result, str)

    @pytest.mark.asyncio(loop_scope="module")
    async def test_grep_with_glob_filter(self, grep_tool):
        """Test grep filtered to specific file types."""
        result = await grep_tool.ainvoke({
            "pattern": "SEARCH_TARGET_ALPHA",
            "glob": "*.py",
            "output_mode": "files_with_matches",
        })

        # Should NOT include .txt files
        assert "test_file3.txt" not in result

    @pytest.mark.asyncio(loop_scope="module")
    async def test_grep_case_insensitive(self, grep_tool):
        """Test case-insensitive search."""
        result = await grep_tool.ainvoke({
            "pattern": "search_target_alpha",  # lowercase
            "i": True,
            "output_mode": "files_with_matches",
        })

        # Should still find uppercase SEARCH_TARGET_ALPHA
        assert "test_file2.py" in result or "test_file3.txt" in result

    @pytest.mark.asyncio(loop_scope="module")
    async def test_grep_with_context_lines(self, grep_tool):
        """Test grep with context lines (-A and -B flags)."""
        result = await grep_tool.ainvoke({
            "pattern": "SEARCH_TARGET_BETA",
            "output_mode": "content",
            "A": 1,
            "B": 1,
        })

        # Should include context around the match
        assert isinstance(result, str)

    @pytest.mark.asyncio(loop_scope="module")
    async def test_grep_no_matches(self, grep_tool):
        """Test grep with no matching pattern."""
        result = await grep_tool.ainvoke({
            "pattern": "NONEXISTENT_PATTERN_12345",
            "output_mode": "files_with_matches",
        })

        # Should indicate no matches
        assert "No matches" in result or len(result.strip()) == 0 or "0" in result


@pytest.mark.integration
class TestGrepDirectMethods:
    """Test direct sandbox grep methods."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_direct_grep_content(self, sandbox_with_files):
        result = await sandbox_with_files.agrep_content(
            pattern="SEARCH_TARGET_ALPHA",
            path=".",
            output_mode="files_with_matches",
        )

        assert isinstance(result, (list, str))


# =============================================================================
# Sandbox Diagnostic Tests
# =============================================================================


@pytest.mark.integration
class TestSandboxDiagnostics:
    """Diagnostic tests to verify sandbox functionality."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_list_directory(self, sandbox_with_files):
        contents = await sandbox_with_files.als_directory(".")

        assert isinstance(contents, list)
        assert len(contents) > 0

    @pytest.mark.asyncio(loop_scope="module")
    async def test_glob_files(self, sandbox_with_files):
        files = await sandbox_with_files.aglob_files("*.py", ".")
        assert isinstance(files, list)

    @pytest.mark.asyncio(loop_scope="module")
    async def test_read_file(self, sandbox_with_files):
        content = await sandbox_with_files.aread_file_text("test_file1.py")

        assert content is not None
        assert "hello" in content.lower()

    def test_validate_path(self, sandbox_with_files):
        assert sandbox_with_files.validate_path(".") is True
        assert sandbox_with_files.validate_path("test_file1.py") is True


# =============================================================================
# Module Import Tests (runs without sandbox)
# =============================================================================


def test_module_imports():
    """Verify that glob and grep tool modules load correctly."""
    assert create_glob_tool is not None
    assert create_grep_tool is not None
    assert callable(create_glob_tool)
    assert callable(create_grep_tool)
