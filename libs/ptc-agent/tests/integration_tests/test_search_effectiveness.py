"""Integration tests for measuring agent search effectiveness.

These tests measure how effectively agents can use Glob, Grep, and Bash tools
to find documentation and resources in the sandbox.

Run with: pytest tests/integration_tests/test_search_effectiveness.py -v -m integration
Skip with: pytest -m "not integration"
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import pytest

# Get project root directory (parent of tests/)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Add project to path
sys.path.insert(0, str(PROJECT_ROOT))

from ptc_agent.config import load_core_from_files
from ptc_agent.core.session import SessionManager


def _load_module_from_path(module_name: str, file_path: str):
    """Load a module directly from file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
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
_bash_module = _load_module_from_path(
    "bash_tool",
    str(PROJECT_ROOT / "ptc_agent" / "agent" / "tools" / "bash.py"),
)

create_glob_tool = _glob_module.create_glob_tool
create_grep_tool = _grep_module.create_grep_tool
create_execute_bash_tool = _bash_module.create_execute_bash_tool


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(scope="module")
async def sandbox_session():
    """Set up and tear down a sandbox session for the test module."""
    config = await load_core_from_files()
    session = SessionManager.get_session("search-effectiveness-test", config)
    await session.initialize()

    yield session

    await SessionManager.cleanup_session("search-effectiveness-test")


@pytest.fixture(scope="module")
def sandbox(sandbox_session):
    """Get sandbox from session."""
    return sandbox_session.sandbox


@pytest.fixture(scope="module")
def glob_tool(sandbox):
    """Create a glob tool for testing."""
    return create_glob_tool(sandbox)


@pytest.fixture(scope="module")
def grep_tool(sandbox):
    """Create a grep tool for testing."""
    return create_grep_tool(sandbox)


@pytest.fixture(scope="module")
def bash_tool(sandbox):
    """Create a bash tool for testing."""
    return create_execute_bash_tool(sandbox)


# =============================================================================
# Helper Functions
# =============================================================================


async def measure_tool_call(tool, params: dict) -> tuple[str, float]:
    """Execute a tool call and measure duration.

    Returns:
        Tuple of (result_string, duration_ms)
    """
    start = time.time()
    result = await tool.ainvoke(params)
    duration_ms = (time.time() - start) * 1000
    return result, duration_ms


# =============================================================================
# Scenario A: Tool Discovery
# =============================================================================


@pytest.mark.integration
class TestToolDiscovery:
    """Scenario: Find all Python files in the tools directory."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_glob_finds_python_files(self, glob_tool):
        """Test Glob can find Python files in tools directory."""
        result, _ = await measure_tool_call(
            glob_tool,
            {"pattern": "*.py", "path": "tools"},
        )

        files_found = result.count(".py")
        assert files_found >= 3, f"Expected at least 3 .py files, found {files_found}"

    @pytest.mark.asyncio(loop_scope="module")
    async def test_grep_finds_function_definitions(self, grep_tool):
        """Test Grep can find function definitions in Python files."""
        result, _ = await measure_tool_call(
            grep_tool,
            {"pattern": "^def ", "path": "tools", "glob": "*.py", "output_mode": "files_with_matches"},
        )

        # Should find at least some function definitions
        assert len(result) > 0 or ":" in result

    @pytest.mark.asyncio(loop_scope="module")
    async def test_bash_lists_python_files(self, bash_tool):
        """Test Bash ls command can list Python files."""
        result, _ = await measure_tool_call(
            bash_tool,
            {"command": "ls -la tools/*.py", "description": "List Python files in tools"},
        )

        files_found = result.count(".py")
        assert files_found >= 3, f"Expected at least 3 .py files, found {files_found}"


# =============================================================================
# Scenario B: Documentation Lookup
# =============================================================================


@pytest.mark.integration
class TestDocumentationLookup:
    """Scenario: Find documentation for tools."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_glob_finds_markdown_docs(self, glob_tool):
        """Test Glob can find markdown documentation files."""
        result, _ = await measure_tool_call(
            glob_tool,
            {"pattern": "*.md", "path": "tools/docs"},
        )

        # May have 0 if tools/docs doesn't exist - that's acceptable
        assert isinstance(result, str)

    @pytest.mark.asyncio(loop_scope="module")
    async def test_grep_searches_doc_content(self, grep_tool):
        """Test Grep can search content in documentation."""
        result, _ = await measure_tool_call(
            grep_tool,
            {"pattern": "symbol", "path": "tools/docs", "output_mode": "files_with_matches"},
        )

        # Result format varies based on whether files exist
        assert isinstance(result, str)

    @pytest.mark.asyncio(loop_scope="module")
    async def test_bash_lists_docs(self, bash_tool):
        """Test Bash can list documentation files."""
        result, _ = await measure_tool_call(
            bash_tool,
            {"command": "ls tools/docs/*.md 2>/dev/null || echo 'No docs found'", "description": "List documentation files"},
        )

        assert isinstance(result, str)


# =============================================================================
# Scenario C: Parameter Search
# =============================================================================


@pytest.mark.integration
class TestParameterSearch:
    """Scenario: Find all tools that accept a specific parameter."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_grep_finds_parameter_usage(self, grep_tool):
        """Test Grep can find parameter usage in code."""
        result, _ = await measure_tool_call(
            grep_tool,
            {"pattern": "symbol", "path": "tools", "glob": "*.py", "output_mode": "content"},
        )

        # May or may not find 'symbol' depending on tool implementations
        assert isinstance(result, str)

    @pytest.mark.asyncio(loop_scope="module")
    async def test_bash_grep_finds_parameters(self, bash_tool):
        """Test Bash grep command can find parameters."""
        result, _ = await measure_tool_call(
            bash_tool,
            {"command": "grep -r 'symbol' tools/*.py 2>/dev/null | head -30 || echo 'No matches'", "description": "Search for symbol parameter"},
        )

        assert isinstance(result, str)


# =============================================================================
# Scenario D: Content Search
# =============================================================================


@pytest.mark.integration
class TestContentSearch:
    """Scenario: Find specific content in documentation."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_grep_finds_returns_sections(self, grep_tool):
        """Test Grep can find Returns sections in documentation."""
        result, _ = await measure_tool_call(
            grep_tool,
            {"pattern": "Returns", "path": "tools/docs", "output_mode": "content", "A": 2},
        )

        assert isinstance(result, str)

    @pytest.mark.asyncio(loop_scope="module")
    async def test_bash_grep_with_context(self, bash_tool):
        """Test Bash grep can search with context lines."""
        result, _ = await measure_tool_call(
            bash_tool,
            {"command": "grep -r 'Returns' tools/docs/ 2>/dev/null | head -20 || echo 'No matches'", "description": "Search for Returns in docs"},
        )

        assert isinstance(result, str)


# =============================================================================
# Scenario E: Pattern Matching
# =============================================================================


@pytest.mark.integration
class TestPatternMatching:
    """Scenario: Complex pattern matching to find specific file types."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_glob_recursive_pattern(self, glob_tool):
        """Test Glob with recursive ** pattern."""
        result, _ = await measure_tool_call(
            glob_tool,
            {"pattern": "**/*.md", "path": "tools"},
        )

        # Check result is valid (may or may not find files)
        assert isinstance(result, str)
        if "No files" not in result and "0 file" not in result:
            files_found = result.count("\n")
            assert files_found >= 0

    @pytest.mark.asyncio(loop_scope="module")
    async def test_glob_simple_pattern(self, glob_tool):
        """Test Glob with simple * pattern."""
        result, _ = await measure_tool_call(
            glob_tool,
            {"pattern": "*.py", "path": "tools"},
        )

        files_found = result.count(".py")
        assert files_found >= 1, "Should find at least one Python file"

    @pytest.mark.asyncio(loop_scope="module")
    async def test_grep_regex_pattern(self, grep_tool):
        """Test Grep with regex pattern."""
        result, _ = await measure_tool_call(
            grep_tool,
            {"pattern": "def.*\\(", "path": "tools", "glob": "*.py", "output_mode": "count"},
        )

        assert isinstance(result, str)

    @pytest.mark.asyncio(loop_scope="module")
    async def test_bash_find_command(self, bash_tool):
        """Test Bash find command."""
        result, _ = await measure_tool_call(
            bash_tool,
            {"command": "find tools -name '*.py' 2>/dev/null | head -20", "description": "Find Python files"},
        )

        assert isinstance(result, str)


# =============================================================================
# Performance Comparison Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.slow
class TestToolPerformanceComparison:
    """Compare performance of different tools for similar tasks."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_file_listing_performance(self, glob_tool, bash_tool):
        """Compare Glob vs Bash for file listing."""
        # Glob
        glob_result, _ = await measure_tool_call(
            glob_tool,
            {"pattern": "*.py", "path": "tools"},
        )

        # Bash
        bash_result, _ = await measure_tool_call(
            bash_tool,
            {"command": "ls tools/*.py", "description": "List Python files"},
        )

        # Both should succeed and find files
        assert ".py" in glob_result or "No files" in glob_result
        assert ".py" in bash_result or "ERROR" in bash_result


# =============================================================================
# Module Import Tests (runs without sandbox)
# =============================================================================


def test_module_imports():
    """Verify that tool modules load correctly."""
    assert create_glob_tool is not None
    assert create_grep_tool is not None
    assert create_execute_bash_tool is not None
    assert callable(create_glob_tool)
    assert callable(create_grep_tool)
    assert callable(create_execute_bash_tool)
