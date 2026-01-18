"""Slash command handlers for the CLI (API mode)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ptc_cli.core import console
from ptc_cli.display import show_help
from ptc_cli.streaming.executor import reconnect_to_workflow

if TYPE_CHECKING:
    from ptc_cli.api.client import SSEStreamClient
    from ptc_cli.core.state import SessionState
    from ptc_cli.display.tokens import TokenTracker


async def handle_command(
    command: str,
    client: SSEStreamClient,
    token_tracker: TokenTracker,
    session_state: SessionState,
) -> str | None:
    """Handle slash commands.

    Args:
        command: The command string (e.g., "/help")
        client: SSE stream client for API communication
        token_tracker: Token tracker for usage display
        session_state: Session state for conversation management

    Returns:
        "exit" if should exit, "handled" if command was processed, None otherwise
    """
    cmd = command.strip()
    cmd_lower = cmd.lower()

    # Exit command
    if cmd_lower in ("/exit", "/q"):
        return "exit"

    if cmd_lower == "/help":
        show_help()

    elif cmd_lower == "/clear":
        # Reset conversation by generating new thread_id
        session_state.reset_thread()
        console.clear()
        console.print("[green]Conversation cleared.[/green]")
        console.print()

    elif cmd_lower == "/tokens":
        token_tracker.display()

    elif cmd_lower == "/model":
        console.print()
        console.print("[yellow]Model selection is not available via API.[/yellow]")
        console.print("[dim]Configure the model in server settings.[/dim]")
        console.print()

    elif cmd_lower in ("/files", "/view", "/copy", "/download") or cmd_lower.startswith(
        ("/files ", "/view ", "/copy ", "/download ")
    ):
        console.print()
        console.print("[yellow]Sandbox commands are not available via API.[/yellow]")
        console.print("[dim]File operations are handled through the agent.[/dim]")
        console.print()

    elif cmd_lower == "/status":
        console.print()

        # Show workflow status if thread_id exists
        if client.thread_id:
            try:
                status = await client.get_workflow_status(client.thread_id)
                console.print(f"[cyan]Thread:[/cyan] {client.thread_id}")
                console.print(f"[cyan]Workflow Status:[/cyan] {status.get('status', 'unknown')}")

                # Show background task info
                active_subagents = status.get("active_subagents", [])
                completed_subagents = status.get("completed_subagents", [])

                if active_subagents:
                    console.print(f"[cyan]Running:[/cyan]")
                    for task in active_subagents:
                        console.print(f"  - {task}")

                if completed_subagents:
                    console.print(f"[cyan]Completed:[/cyan]")
                    for task in completed_subagents:
                        console.print(f"  - {task}")

                if status.get("soft_interrupted"):
                    console.print("[yellow]Workflow was soft-interrupted (subagents may still be running)[/yellow]")

            except Exception as e:
                console.print(f"[dim]Thread: {client.thread_id}[/dim]")
                console.print(f"[dim]Could not get workflow status: {e}[/dim]")
        else:
            console.print("[dim]No active workflow thread[/dim]")

        console.print()

        # Show workspace status if workspace_id exists
        if client.workspace_id:
            try:
                workspace = await client.get_workspace(client.workspace_id)
                if workspace:
                    console.print(f"[cyan]Workspace:[/cyan] {workspace.get('name', 'N/A')}")
                    console.print(f"[cyan]Workspace ID:[/cyan] {workspace.get('workspace_id', 'N/A')}")
                    console.print(f"[cyan]Workspace Status:[/cyan] {workspace.get('status', 'N/A')}")
                else:
                    console.print("[dim]Workspace not found[/dim]")
            except Exception as e:
                console.print(f"[dim]Could not get workspace status: {e}[/dim]")

        console.print(f"[cyan]Server:[/cyan] {client.base_url}")
        console.print()

    elif cmd_lower == "/cancel":
        # Cancel running workflow
        if client.thread_id:
            try:
                await client.cancel_workflow(client.thread_id)
                console.print("[green]Workflow cancelled[/green]")
            except Exception as e:
                console.print(f"[yellow]Could not cancel workflow: {e}[/yellow]")
        else:
            console.print("[yellow]No active workflow to cancel[/yellow]")

    elif cmd_lower == "/reconnect":
        # Reconnect to running workflow (useful after ESC interrupt)
        from ptc_cli.core.state import ReconnectStateManager

        state_manager = ReconnectStateManager()

        if session_state.thread_id:
            # Load last_event_id from saved state
            saved_state = state_manager.load_state(session_state.thread_id)
            if saved_state:
                client.last_event_id = saved_state.get("last_event_id", 0)
            await reconnect_to_workflow(client, session_state, token_tracker)
        else:
            # Try to load latest session
            latest_thread = state_manager.get_latest_thread_id()
            if latest_thread:
                session_state.thread_id = latest_thread
                client.thread_id = latest_thread
                saved_state = state_manager.load_state(latest_thread)
                if saved_state:
                    client.last_event_id = saved_state.get("last_event_id", 0)
                console.print(f"[dim]Loaded session: {latest_thread[:16]}...[/dim]")
                await reconnect_to_workflow(client, session_state, token_tracker)
            else:
                console.print("[yellow]No workflow sessions to reconnect to[/yellow]")
                console.print("[dim]Start a task first, then use ESC to soft-interrupt.[/dim]")

    else:
        # Unknown command
        console.print(f"[yellow]Unknown command: {command}[/yellow]")
        console.print("[dim]Available: /help, /clear, /tokens, /status, /cancel, /reconnect, /exit[/dim]")

    return "handled"
