"""Sandbox recovery utilities for handling disconnections during active sessions."""

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from ptc_agent.core.session import Session
    from rich.console import Console

logger = structlog.get_logger(__name__)

# Error patterns that indicate sandbox disconnection
SANDBOX_ERROR_PATTERNS = [
    # Connection errors
    "connection refused",
    "sandbox not initialized",
    "failed to connect",
    "socket closed",
    "timeout",
    "sandbox not found",
    "connection reset",
    "broken pipe",
    "network unreachable",
    "no route to host",
    # Daytona API errors (sandbox stopped)
    "400 bad request",
    "bad request",  # Without "400" prefix (Daytona sometimes omits status code)
    "failed to upload",
    "toolbox",
    "502 bad gateway",
    "503 service unavailable",
    "504 gateway timeout",
    # Daytona sandbox state errors
    "no ip address",  # Sandbox not started/available
    "is the sandbox started",  # Daytona hint message
    "sandbox is not started",  # Stop error when already stopped
]


def is_sandbox_error(error_message: str) -> bool:
    """Check if an error message indicates sandbox disconnection.

    Args:
        error_message: Error message from tool execution

    Returns:
        True if error appears to be sandbox-related
    """
    error_lower = error_message.lower()
    return any(pattern in error_lower for pattern in SANDBOX_ERROR_PATTERNS)


async def recover_sandbox(session: "Session", console: "Console") -> bool:
    """Attempt to recover a disconnected sandbox.

    First tries to reconnect to the existing sandbox. If that fails
    (e.g., sandbox was deleted), creates a new sandbox.

    Args:
        session: The Session object containing the sandbox
        console: Rich console for status output

    Returns:
        True if recovery successful, False otherwise
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn

    if session is None or session.sandbox is None:
        console.print("[red]No session to recover[/red]")
        return False

    sandbox_id = getattr(session.sandbox, "sandbox_id", None)
    if sandbox_id is None:
        console.print("[red]No sandbox ID to reconnect to[/red]")
        return False

    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Reconnecting to sandbox...", total=None)

        try:
            # Try to reconnect to existing sandbox
            await session.sandbox.reconnect(sandbox_id)
            progress.update(task, description="Reconnected!")

        except Exception as reconnect_error:  # noqa: BLE001
            # Sandbox may have been deleted - try creating new one
            logger.warning(
                "Reconnect failed, creating new sandbox",
                sandbox_id=sandbox_id,
                error=str(reconnect_error),
            )
            progress.update(task, description="Creating new sandbox...")

            try:
                # Reset session and create fresh sandbox
                session._initialized = False
                session.sandbox = None
                await session.initialize()

                console.print("[yellow]Note: Previous workspace state was lost[/yellow]")

            except Exception as create_error:
                logger.exception(
                    "Failed to create new sandbox",
                    error=str(create_error),
                )
                console.print(f"[red]Failed to recover: {create_error}[/red]")
                console.print("[dim]Please restart the CLI[/dim]")
                return False

    console.print("[green]✓ Sandbox recovered[/green]")
    return True
