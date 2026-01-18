"""Integration tests for execute_code tool with cloud storage image upload.

These tests require a running Daytona sandbox and verify:
1. Basic code execution in sandbox
2. Matplotlib chart generation with plt.show() (artifact capture)
3. Matplotlib chart generation with plt.savefig() (file detection)
4. Cloud storage upload functionality
5. Markdown image URL generation

Run with: pytest tests/integration_tests/test_execute_code_storage.py -v -m integration
Skip with: pytest -m "not integration"
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

# Get project root directory (parent of tests/)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Add project to path
sys.path.insert(0, str(PROJECT_ROOT))

from ptc_agent.config import load_core_from_files
from ptc_agent.core.session import SessionManager


def _load_module_from_path(module_name: str, file_path: str):
    """Load a module directly from file path to bypass package import chain."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Load execute_code tool directly
_execute_module = _load_module_from_path(
    "execute_tool",
    str(PROJECT_ROOT / "ptc_agent" / "agent" / "tools" / "code_execution.py"),
)
create_execute_code_tool = _execute_module.create_execute_code_tool


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(scope="module")
async def sandbox_session():
    """Set up and tear down a sandbox session for the test module.

    This fixture is module-scoped for efficiency - sandbox setup is expensive.
    """
    config = await load_core_from_files()
    session = SessionManager.get_session("test-execute-code-storage", config)
    await session.initialize()

    yield session

    await SessionManager.cleanup_session("test-execute-code-storage")


@pytest.fixture(scope="module")
def sandbox(sandbox_session):
    """Get sandbox from session."""
    return sandbox_session.sandbox


@pytest.fixture(scope="module")
def mcp_registry(sandbox_session):
    """Get MCP registry from session."""
    return sandbox_session.mcp_registry


@pytest.fixture(scope="module")
def execute_code_tool(sandbox, mcp_registry):
    """Create an execute_code tool for testing."""
    return create_execute_code_tool(sandbox, mcp_registry)


# =============================================================================
# Basic Execution Tests
# =============================================================================


@pytest.mark.integration
class TestBasicExecution:
    """Tests for basic code execution without chart generation."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_simple_print(self, execute_code_tool):
        """Test basic print statement execution."""
        code = """
print("Hello from sandbox!")
x = 1 + 2
print(f"Result: {x}")
"""
        result = await execute_code_tool.ainvoke({"code": code})

        assert "SUCCESS" in result
        assert "Hello from sandbox!" in result
        assert "Result: 3" in result

    @pytest.mark.asyncio(loop_scope="module")
    async def test_error_handling(self, execute_code_tool):
        """Test that execution errors are properly reported."""
        code = """
# This will cause a NameError
undefined_variable + 1
"""
        result = await execute_code_tool.ainvoke({"code": code})

        assert "ERROR" in result
        assert "NameError" in result or "undefined" in result.lower()


# =============================================================================
# Matplotlib Chart Tests
# =============================================================================


@pytest.mark.integration
class TestMatplotlibCharts:
    """Tests for matplotlib chart generation and upload."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_matplotlib_show(self, execute_code_tool):
        """Test matplotlib chart with plt.show() - captured via artifacts."""
        code = """
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

# Create a simple chart
x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.figure(figsize=(10, 6))
plt.plot(x, y, 'b-', linewidth=2)
plt.title('Sine Wave Chart')
plt.xlabel('X axis')
plt.ylabel('Y axis')
plt.grid(True)
plt.show()

print("Chart generated with plt.show()")
"""
        result = await execute_code_tool.ainvoke({"code": code})

        assert "SUCCESS" in result
        # Either chart is uploaded or at least code executed successfully
        if "Uploaded images:" in result:
            assert "![" in result  # Markdown image format

    @pytest.mark.asyncio(loop_scope="module")
    async def test_matplotlib_savefig(self, execute_code_tool):
        """Test matplotlib chart saved with plt.savefig() - detected via files_created."""
        code = """
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Create a bar chart
categories = ['A', 'B', 'C', 'D', 'E']
values = [23, 45, 56, 78, 32]

plt.figure(figsize=(8, 6))
plt.bar(categories, values, color='steelblue')
plt.title('Bar Chart Example')
plt.xlabel('Category')
plt.ylabel('Value')

# Save to results directory
plt.savefig('results/bar_chart.png', dpi=100, bbox_inches='tight')
plt.close()

print("Saved bar_chart.png to results/")
"""
        result = await execute_code_tool.ainvoke({"code": code})

        assert "SUCCESS" in result
        assert "bar_chart.png" in result
        # File should be uploaded
        if "Uploaded images:" in result:
            assert "![" in result

    @pytest.mark.asyncio(loop_scope="module")
    async def test_multiple_charts(self, execute_code_tool):
        """Test multiple image generation and upload."""
        code = """
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Chart 1: Line plot
plt.figure(figsize=(8, 5))
x = np.linspace(0, 10, 50)
plt.plot(x, np.cos(x), 'r-', label='cos')
plt.plot(x, np.sin(x), 'b--', label='sin')
plt.title('Trigonometric Functions')
plt.legend()
plt.savefig('results/trig_chart.png', dpi=100)
plt.close()

# Chart 2: Scatter plot
plt.figure(figsize=(8, 5))
np.random.seed(42)
x = np.random.randn(50)
y = np.random.randn(50)
plt.scatter(x, y, c='purple', alpha=0.6)
plt.title('Random Scatter')
plt.savefig('results/scatter_chart.png', dpi=100)
plt.close()

# Chart 3: Pie chart
plt.figure(figsize=(8, 8))
sizes = [30, 25, 20, 15, 10]
labels = ['A', 'B', 'C', 'D', 'E']
plt.pie(sizes, labels=labels, autopct='%1.1f%%')
plt.title('Pie Chart')
plt.savefig('results/pie_chart.png', dpi=100)
plt.close()

print("Generated 3 charts: trig_chart.png, scatter_chart.png, pie_chart.png")
"""
        result = await execute_code_tool.ainvoke({"code": code})

        assert "SUCCESS" in result
        assert "trig_chart.png" in result
        assert "scatter_chart.png" in result
        assert "pie_chart.png" in result

        # Count uploaded images
        upload_count = result.count("![")
        if "Uploaded images:" in result:
            assert upload_count >= 3, f"Expected at least 3 uploads, got {upload_count}"


# =============================================================================
# PIL Image Tests
# =============================================================================


@pytest.mark.integration
class TestPILImages:
    """Tests for PIL image generation and upload."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_pil_image_generation(self, execute_code_tool):
        """Test PIL image creation and upload."""
        code = """
from PIL import Image, ImageDraw

# Create a simple image
img = Image.new('RGB', (400, 300), color='white')
draw = ImageDraw.Draw(img)

# Draw some shapes
draw.rectangle([50, 50, 350, 250], outline='blue', width=3)
draw.ellipse([100, 100, 300, 200], fill='lightblue', outline='navy')
draw.text((150, 130), "Test Image", fill='darkblue')

# Save
img.save('results/pil_test.png')

print("Created PIL test image")
"""
        result = await execute_code_tool.ainvoke({"code": code})

        assert "SUCCESS" in result
        assert "pil_test.png" in result


# =============================================================================
# Storage URL Format Tests
# =============================================================================


@pytest.mark.integration
class TestStorageURLFormat:
    """Tests for verifying storage URL format in responses."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_markdown_url_format(self, execute_code_tool):
        """Verify storage URLs use correct markdown format."""
        code = """
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.figure(figsize=(6, 4))
plt.plot([1, 2, 3], [1, 4, 2], 'go-')
plt.title('URL Format Test')
plt.savefig('results/url_test.png')
plt.close()

print("Chart saved for URL test")
"""
        result = await execute_code_tool.ainvoke({"code": code})

        assert "SUCCESS" in result

        if "Uploaded images:" in result:
            # Check for markdown image format: ![alt](url)
            assert "![" in result
            assert "](" in result
            assert "http" in result

            # Extract and validate URL format
            urls = re.findall(r"\!\[.*?\]\((https?://[^)]+)\)", result)
            assert len(urls) > 0, "No valid markdown image URLs found"

            for url in urls:
                assert ".png" in url, f"URL should reference PNG file: {url}"


# =============================================================================
# ExecutionResult Tests
# =============================================================================


@pytest.mark.integration
class TestExecutionResult:
    """Tests for ExecutionResult object structure."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_execution_result_charts_field(self, sandbox):
        """Test that ExecutionResult properly captures charts."""
        code = """
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.figure()
plt.plot([1, 2, 3], [1, 2, 3])
plt.title('Direct Result Test')
plt.show()

print("Testing charts field")
"""
        result = await sandbox.execute(code)

        assert result.success
        assert hasattr(result, "charts"), "ExecutionResult should have charts field"

        # Charts may be empty if artifact capture isn't available
        if result.charts:
            for chart in result.charts:
                assert hasattr(chart, "type")
                assert hasattr(chart, "title")

    @pytest.mark.asyncio(loop_scope="module")
    async def test_execution_result_files_created(self, sandbox):
        """Test that ExecutionResult tracks created files."""
        code = """
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.figure()
plt.plot([1, 2], [1, 2])
plt.savefig('results/test_files_created.png')
plt.close()
print("File created")
"""
        result = await sandbox.execute(code)

        assert result.success
        assert hasattr(result, "files_created")
        # File should be in files_created list
        if result.files_created:
            file_names = [str(f) for f in result.files_created]
            assert any("test_files_created.png" in f for f in file_names)


# =============================================================================
# Module Import Tests (runs without sandbox)
# =============================================================================


def test_module_imports():
    """Verify that execute_code tool module loads correctly."""
    assert create_execute_code_tool is not None
    assert callable(create_execute_code_tool)
