"""HTTP error handling utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from rich.console import Console


def parse_error_detail(response: httpx.Response) -> str | None:
    """Extract error detail from an HTTP response.

    Args:
        response: The HTTP response object

    Returns:
        The error detail string if present, None otherwise
    """
    try:
        return response.json().get("detail")
    except Exception:
        return None


def handle_http_error(
    e: httpx.HTTPStatusError,
    console: "Console",
    *,
    context: str | None = None,
) -> None:
    """Handle HTTPStatusError with consistent formatting.

    Args:
        e: The HTTPStatusError exception
        console: Rich console for output
        context: Optional context message (e.g., "downloading file")
    """
    detail = parse_error_detail(e.response)
    msg = detail or f"HTTP {e.response.status_code}"

    if context:
        console.print(f"[red]{context}: {msg}[/red]")
    else:
        console.print(f"[red]{msg}[/red]")
