.PHONY: install test test-unit test-integration lint format clean help

help:
	@echo "Available targets:"
	@echo "  install          - Install dependencies with uv sync"
	@echo "  test             - Run all tests"
	@echo "  test-unit        - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  lint             - Run linters (ruff, mypy)"
	@echo "  format           - Format code with black and ruff"
	@echo "  clean            - Clean build artifacts"

install:
	uv sync

test:
	uv run pytest tests/ -v

test-unit:
	uv run pytest tests/unit_tests/ -v

test-integration:
	uv run pytest tests/integration_tests/ -v

lint:
	uv run ruff check ptc_agent/ tests/
	uv run mypy ptc_agent/

format:
	uv run black ptc_agent/ tests/
	uv run ruff check --fix ptc_agent/ tests/

clean:
	rm -rf .venv __pycache__ .pytest_cache .mypy_cache .ruff_cache *.egg-info dist build
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
