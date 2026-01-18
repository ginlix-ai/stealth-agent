# pyright: reportGeneralTypeIssues=false
"""Task execution and streaming logic for the CLI (API mode)."""

import asyncio
import json
import os
import select
import sys
import threading
from collections.abc import Callable
from contextlib import suppress
from typing import TYPE_CHECKING, Any

import httpx
import structlog
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax

from ptc_cli.api.client import SSEStreamClient
from ptc_cli.core import COLORS, console, get_syntax_theme
from ptc_cli.display import (
    TokenTracker,
    format_tool_display,
    render_todo_list,
    truncate_error,
)
from ptc_cli.streaming.state import StreamingState

termios: Any | None
tty: Any | None
try:
    import termios
    import tty
except ImportError:  # pragma: no cover
    termios = None
    tty = None

if TYPE_CHECKING:
    from ptc_cli.core.state import SessionState

logger = structlog.get_logger(__name__)


class _EscInterruptWatcher:
    """Watches for ESC key presses during streaming.

    prompt-toolkit keybindings only work while PromptSession is active. During streaming
    we need a separate watcher so users can interrupt with ESC.

    When ESC is pressed, this watcher:
    1. Calls the soft_interrupt API (keeps background subagents running)
    2. Stores the result for display
    3. Cancels the local streaming task
    """

    def __init__(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        on_escape: Callable[[], None],
        client: "SSEStreamClient | None" = None,
        session_state: "SessionState | None" = None,
    ) -> None:
        self._loop = loop
        self._on_escape = on_escape
        self._client = client
        self._session_state = session_state
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        if not sys.stdin.isatty() or termios is None or tty is None:
            return

        self._thread = threading.Thread(target=self._run, name="esc_interrupt_watcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=0.5)

    def _run(self) -> None:
        if termios is None or tty is None:
            return

        fd = sys.stdin.fileno()
        try:
            old_attrs = termios.tcgetattr(fd)
        except OSError:
            return

        try:
            tty.setcbreak(fd)
            while not self._stop.is_set():
                readable, _w, _x = select.select([fd], [], [], 0.1)
                if not readable:
                    continue

                ch = os.read(fd, 1)
                if ch == b"\x1b":  # ESC
                    # Call soft_interrupt API (keeps subagents running)
                    self._call_soft_interrupt()
                    # Then cancel local task
                    with suppress(Exception):
                        self._loop.call_soon_threadsafe(self._on_escape)
                    return
        finally:
            with suppress(Exception):
                termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)

    def _call_soft_interrupt(self) -> None:
        """Call soft_interrupt API from background thread."""
        if not self._client or not self._session_state:
            return

        thread_id = getattr(self._session_state, "thread_id", None)
        if not thread_id:
            return

        try:
            # Schedule async API call on event loop and wait for result
            future = asyncio.run_coroutine_threadsafe(
                self._client.soft_interrupt(thread_id),
                self._loop
            )
            # Wait for result with timeout (don't block forever)
            result = future.result(timeout=2.0)
            # Store result for display in CancelledError handler
            if self._session_state:
                self._session_state.soft_interrupt_result = result
        except Exception as e:
            # Log but don't fail - we still want to interrupt
            logger.debug(f"Soft interrupt API call failed: {e}")


async def _prompt_for_plan_approval(action_request: dict) -> tuple[dict, str | None]:
    """Show plan and prompt user for approval with arrow key navigation.

    Args:
        action_request: The action request from HITL interrupt

    Returns:
        Tuple of (decision dict, feedback string or None)
        - decision: Dict with 'type' key ('approve' or 'reject')
        - feedback: User feedback for rejection, or None for approval/cancel
    """
    from prompt_toolkit import PromptSession
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    from ptc_cli.core import console

    description = action_request.get("description", "No description available")

    # Display the plan for review with markdown rendering
    console.print()
    md_content = Markdown(description)
    console.print(
        Panel(
            md_content,
            title="[bold cyan]Plan Review[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )
    console.print()

    # Arrow key menu
    options = ["Accept", "Reject with feedback"]
    selected = [0]  # Use list to allow modification in nested function

    def get_menu_text() -> str:
        lines = []
        for i, option in enumerate(options):
            if i == selected[0]:
                lines.append(f"  > {option}")
            else:
                lines.append(f"    {option}")
        lines.append("")
        lines.append("  (Up/Down to navigate, Enter to select)")
        return "\n".join(lines)

    kb = KeyBindings()

    @kb.add("up")
    def _(_event: object) -> None:
        selected[0] = max(0, selected[0] - 1)

    @kb.add("down")
    def _(_event: object) -> None:
        selected[0] = min(len(options) - 1, selected[0] + 1)

    @kb.add("enter")
    def _(event: "Any") -> None:  # noqa: ANN401
        event.app.exit(result=selected[0])

    @kb.add("c-c")
    def _(event: "Any") -> None:  # noqa: ANN401
        event.app.exit(result=-1)  # Cancelled

    layout = Layout(Window(FormattedTextControl(get_menu_text)))
    app: Application[int] = Application(layout=layout, key_bindings=kb, full_screen=False)

    try:
        result = await app.run_async()
    except KeyboardInterrupt:
        result = -1

    if result == -1:  # Cancelled
        console.print()
        return {"type": "reject"}, "User cancelled"
    if result == 0:  # Accept
        console.print()
        console.print("[green]Plan approved. Starting execution...[/green]")
        return {"type": "approve"}, None
    # Reject with feedback
    console.print()
    try:
        feedback_session: PromptSession[str] = PromptSession()
        feedback = await feedback_session.prompt_async("  Feedback: ")
    except KeyboardInterrupt:
        return {"type": "reject"}, "User cancelled"
    else:
        return {"type": "reject"}, (feedback or "No feedback provided")


# Tool display icons
TOOL_ICONS = {
    "read_file": "📖",
    "write_file": "✏️",
    "edit_file": "✂️",
    "ls": "📁",
    "glob": "🔍",
    "grep": "🔎",
    "shell": "⚡",
    "execute": "🔧",
    "execute_code": "🔧",
    "Bash": "⚡",
    "Read": "📖",
    "Write": "✏️",
    "Edit": "✂️",
    "Glob": "🔍",
    "Grep": "🔎",
    "web_search": "🌐",
    "http_request": "🌍",
    "task": "🤖",
    "wait": "⏳",
    "task_output": "📤",
    "write_todos": "📋",
    "submit_plan": "📋",
}


async def execute_task(
    user_input: str,
    client: SSEStreamClient,
    assistant_id: str | None,
    session_state: "SessionState",
    token_tracker: TokenTracker | None = None,
) -> None:
    """Execute task via server API.

    Args:
        user_input: User's input text
        client: SSE stream client for API communication
        assistant_id: Agent identifier
        session_state: Session state with settings
        token_tracker: Optional token tracker
    """
    from ptc_cli.core.state import ReconnectStateManager

    todo_state: dict[str, list | None] = {"todos": None}
    tool_name_by_id: dict[str, str] = {}
    event_count = 0  # Track events for periodic state saving
    state_manager = ReconnectStateManager()

    # Clear soft_interrupted flag when starting new task (seamless continuation)
    if hasattr(session_state, "soft_interrupted"):
        session_state.soft_interrupted = False
    if hasattr(session_state, "soft_interrupt_result"):
        session_state.soft_interrupt_result = None

    # Initialize streaming state
    state = StreamingState(console, f"[bold {COLORS['thinking']}]Agent is thinking...", COLORS)

    # Build HITL response if pending (from previous interrupt)
    hitl_response = None
    if hasattr(session_state, "pending_hitl_response") and session_state.pending_hitl_response:
        hitl_response = session_state.pending_hitl_response
        session_state.pending_hitl_response = None

    # Allow ESC to interrupt the foreground stream
    loop = asyncio.get_running_loop()
    this_task = asyncio.current_task()

    def _on_escape() -> None:
        session_state.esc_interrupt_requested = True
        if this_task is not None:
            this_task.cancel()

    esc_watcher = _EscInterruptWatcher(
        loop=loop,
        on_escape=_on_escape,
        client=client,
        session_state=session_state,
    )
    esc_watcher.start()

    try:
        # Stream from API
        async for event_type, event_data in client.stream_chat(
            message=user_input,
            thread_id=session_state.thread_id,
            hitl_response=hitl_response,
            plan_mode=getattr(session_state, "plan_mode", False),
        ):
            # Track thread_id from events
            if "thread_id" in event_data:
                session_state.thread_id = event_data["thread_id"]
                client.thread_id = event_data["thread_id"]

            # Periodic state saving (every 10 events)
            event_count += 1
            if event_count % 10 == 0 and client.last_event_id > 0:
                state_manager.save_state(
                    session_state.thread_id,
                    client.last_event_id,
                    {"query": user_input[:100], "workspace_id": client.workspace_id},
                )

            # Handle different event types
            if event_type == "message_chunk":
                _handle_message_chunk(event_data, state)

            elif event_type == "tool_calls":
                for tool_call in event_data.get("tool_calls", []) or []:
                    tool_call_id = tool_call.get("id")
                    tool_name = tool_call.get("name")
                    if tool_call_id and tool_name:
                        tool_name_by_id[tool_call_id] = tool_name
                _handle_tool_calls(event_data, state, todo_state)

            elif event_type == "tool_call_result":
                _handle_tool_result(event_data, state, tool_name_by_id)

            elif event_type == "tool_call_chunks":
                # Animation only - args come complete in tool_calls
                pass

            elif event_type == "interrupt":
                # HITL - prompt for approval
                if state.spinner_active:
                    state.stop_spinner()

                interrupt_id = event_data.get("interrupt_id", "default")
                action_requests = event_data.get("action_requests", [])

                # Check for auto-approve
                if getattr(session_state, "auto_approve", False):
                    decisions = [{"type": "approve"} for _ in action_requests]
                    console.print()
                    console.print("[dim]Auto-approved plan[/dim]")
                else:
                    # Prompt user for each action
                    decisions = []
                    esc_watcher.stop()
                    try:
                        for action_request in action_requests:
                            decision, feedback = await _prompt_for_plan_approval(action_request)
                            if decision.get("type") == "reject" and feedback:
                                decision["message"] = feedback
                            decisions.append(decision)
                    finally:
                        esc_watcher.stop()

                # Store response for resume
                session_state.pending_hitl_response = {
                    interrupt_id: {"decisions": decisions}
                }

                if state.spinner_active:
                    state.stop_spinner()
                esc_watcher.stop()
                console.print()
                return await execute_task(
                    user_input="",
                    client=client,
                    assistant_id=assistant_id,
                    session_state=session_state,
                    token_tracker=token_tracker,
                )


            elif event_type == "error":
                state.flush_text(final=True)
                if state.spinner_active:
                    state.stop_spinner()
                error_msg = event_data.get("error", "Unknown error")
                console.print()
                console.print(f"[red]Error: {error_msg}[/red]")
                console.print()
                break

            elif event_type == "done":
                break

            elif event_type == "keepalive":
                # Heartbeat - ignore
                pass

            elif event_type == "subagent_status":
                # Update session state with background task status
                session_state.background_status = {
                    "active_subagents": event_data.get("active_subagents", []),
                    "completed_subagents": event_data.get("completed_subagents", []),
                }
                # Update spinner to show count
                active_count = len(event_data.get("active_subagents", []))
                if active_count > 0 and state.spinner_active:
                    label = "subagent" if active_count == 1 else "subagents"
                    state.update_spinner(f"[bold {COLORS['thinking']}]{active_count} {label} running...")

        # After streaming
        state.flush_text(final=True)

        # Save final state for reconnection
        if client.last_event_id > 0:
            state_manager.save_state(
                session_state.thread_id,
                client.last_event_id,
                {"query": user_input[:100], "workspace_id": client.workspace_id},
            )

    except asyncio.CancelledError:
        # ESC interrupt
        if getattr(session_state, "esc_interrupt_requested", False):
            session_state.esc_interrupt_requested = False
            if state.spinner_active:
                state.stop_spinner()

            # Save state for reconnection
            if client.last_event_id > 0:
                state_manager.save_state(
                    session_state.thread_id,
                    client.last_event_id,
                    {"query": user_input[:100], "workspace_id": client.workspace_id},
                )

            # Check soft interrupt result for background task info
            soft_interrupt_result = getattr(session_state, "soft_interrupt_result", None)
            if soft_interrupt_result:
                # Clear the result
                session_state.soft_interrupt_result = None

                active_subagents = (
                    soft_interrupt_result.get("active_subagents")
                    or soft_interrupt_result.get("background_tasks")
                    or []
                )
                if active_subagents:
                    console.print(f"\n[yellow]Interrupted (ESC)[/yellow]")
                    console.print(f"[dim]{len(active_subagents)} background task(s) still running[/dim]")
                    console.print(f"[dim]Use /reconnect or ptc-agent --reconnect to resume[/dim]")

                    # Store for status bar display
                    session_state.soft_interrupted = True
                    session_state.background_status = {
                        "active_subagents": active_subagents,
                        "completed_subagents": soft_interrupt_result.get("completed_subagents", []),
                    }
                else:
                    console.print("\n[yellow]Interrupted (Esc)[/yellow]")
            else:
                console.print("\n[yellow]Interrupted (Esc)[/yellow]")

            return None
        raise

    except KeyboardInterrupt:
        raise

    except Exception as e:
        if state.spinner_active:
            state.stop_spinner()
        console.print()

        if isinstance(e, httpx.HTTPStatusError) and e.response is not None:
            if e.response.status_code == 409:
                console.print("[yellow]Workflow still running[/yellow]")
                console.print("[dim]Use /reconnect to continue, or /cancel to stop it.[/dim]")
                console.print()
                return None

        console.print(f"[red]Error: {e}[/red]")
        console.print()
        return None

    finally:
        esc_watcher.stop()

    if state.spinner_active:
        state.stop_spinner()

    if state.has_responded:
        console.print()

    return None


async def reconnect_to_workflow(
    client: SSEStreamClient,
    session_state: "SessionState",
    token_tracker: TokenTracker | None = None,
) -> None:
    """Reconnect to a running workflow and stream remaining events.

    Use this after ESC interrupt to see remaining output from a running workflow.

    Args:
        client: SSE stream client for API communication
        session_state: Session state with thread_id
        token_tracker: Optional token tracker
    """
    thread_id = session_state.thread_id
    if not thread_id:
        console.print("[yellow]No active workflow thread to reconnect to[/yellow]")
        return

    todo_state: dict[str, list | None] = {"todos": None}
    tool_name_by_id: dict[str, str] = {}

    # Initialize streaming state
    state = StreamingState(console, f"[bold {COLORS['thinking']}]Reconnecting...", COLORS)
    state.start_spinner()

    # Allow ESC to interrupt the reconnection stream
    loop = asyncio.get_running_loop()
    this_task = asyncio.current_task()

    def _on_escape() -> None:
        session_state.esc_interrupt_requested = True
        if this_task is not None:
            this_task.cancel()

    esc_watcher = _EscInterruptWatcher(
        loop=loop,
        on_escape=_on_escape,
        client=client,
        session_state=session_state,
    )
    esc_watcher.start()

    try:
        console.print(f"[dim]Reconnecting to workflow {thread_id[:8]}...[/dim]")
        console.print()

        # Stream from reconnect endpoint
        async for event_type, event_data in client.reconnect_to_stream(
            thread_id=thread_id,
            last_event_id=client.last_event_id,
        ):
            # Handle different event types (same as execute_task)
            if event_type == "message_chunk":
                _handle_message_chunk(event_data, state)

            elif event_type == "tool_calls":
                for tool_call in event_data.get("tool_calls", []) or []:
                    tool_call_id = tool_call.get("id")
                    tool_name = tool_call.get("name")
                    if tool_call_id and tool_name:
                        tool_name_by_id[tool_call_id] = tool_name
                _handle_tool_calls(event_data, state, todo_state)

            elif event_type == "tool_call_result":
                _handle_tool_result(event_data, state, tool_name_by_id)

            elif event_type == "error":
                state.flush_text(final=True)
                if state.spinner_active:
                    state.stop_spinner()
                error_msg = event_data.get("error", "Unknown error")
                console.print()
                console.print(f"[red]Error: {error_msg}[/red]")
                console.print()
                break

            elif event_type == "done":
                # Workflow completed
                session_state.soft_interrupted = False
                break

            elif event_type == "keepalive":
                pass

            elif event_type == "subagent_status":
                session_state.background_status = {
                    "active_subagents": event_data.get("active_subagents", []),
                    "completed_subagents": event_data.get("completed_subagents", []),
                }
                active_count = len(event_data.get("active_subagents", []))
                if active_count > 0 and state.spinner_active:
                    label = "subagent" if active_count == 1 else "subagents"
                    state.update_spinner(f"[bold {COLORS['thinking']}]{active_count} {label} running...")

        # After streaming
        state.flush_text(final=True)
        console.print()
        console.print("[green]Workflow completed[/green]")

    except asyncio.CancelledError:
        if getattr(session_state, "esc_interrupt_requested", False):
            session_state.esc_interrupt_requested = False
            if state.spinner_active:
                state.stop_spinner()
            console.print("\n[yellow]Disconnected (Esc)[/yellow]")
            return None
        raise

    except httpx.HTTPStatusError as e:
        if state.spinner_active:
            state.stop_spinner()
        console.print()
        if e.response.status_code == 404:
            console.print("[yellow]Workflow not found on server[/yellow]")
            console.print("[dim]The workflow may have completed or the server was restarted.[/dim]")
            console.print("[dim]Workflows are available for 24 hours after completion.[/dim]")
        elif e.response.status_code == 410:
            console.print("[yellow]Workflow expired[/yellow]")
            console.print("[dim]Results are only available for 24 hours after completion.[/dim]")
        else:
            console.print(f"[red]Reconnection error: HTTP {e.response.status_code}[/red]")
        console.print()
        return None

    except Exception as e:
        if state.spinner_active:
            state.stop_spinner()
        console.print()
        console.print(f"[red]Reconnection error: {e}[/red]")
        console.print()
        return None

    finally:
        esc_watcher.stop()

    if state.spinner_active:
        state.stop_spinner()

    if state.has_responded:
        console.print()

    return None


def _handle_message_chunk(data: dict, state: StreamingState) -> None:
    """Handle message_chunk event."""
    agent = str(data.get("agent", ""))
    if "tools:" in agent:
        # Hide subagent/tool-node streaming output in the CLI.
        return

    content_type = data.get("content_type", "text")
    content = data.get("content", "")

    # Handle reasoning signal
    if content_type == "reasoning_signal":
        if content == "start":
            console.print(f"[magenta dim]Reasoning...[/magenta dim]")
        elif content == "complete":
            console.print()
            console.print("[green]Reasoning complete[/green]")
        return

    # Handle text/reasoning content
    if content:
        if content_type == "reasoning":
            # Display reasoning with different styling
            console.print(f"[dim italic magenta]{content}[/dim italic magenta]", end="")
        else:
            # Regular text
            state.append_text(content)

    # Handle finish
    if data.get("finish_reason"):
        state.flush_text(final=True)


def _handle_tool_calls(data: dict, state: StreamingState, todo_state: dict[str, list | None]) -> None:
    """Handle tool_calls event.

    Todo list updates are rendered from the `write_todos` tool args.
    """
    agent = str(data.get("agent", ""))
    if "tools:" in agent:
        # Hide subagent/tool-node tool call displays in the CLI.
        return

    state.flush_text(final=True)
    if state.spinner_active:
        state.stop_spinner()

    tool_calls = data.get("tool_calls", [])
    for tool in tool_calls:
        tool_name = tool.get("name", "unknown")
        tool_args = tool.get("args", {})

        icon = TOOL_ICONS.get(tool_name, "🔧")
        display_str = format_tool_display(tool_name, tool_args)

        if state.has_responded:
            console.print()

        console.print(
            f"  {icon} {display_str}",
            style=f"dim {COLORS['tool']}",
            markup=False,
        )

        if tool_name == "write_todos":
            todos = tool_args.get("todos") if isinstance(tool_args, dict) else None
            if isinstance(todos, list) and todos and todos != todo_state.get("todos"):
                todo_state["todos"] = todos
                console.print()
                render_todo_list(todos)
                console.print()

    # Restart spinner
    state.update_spinner(f"[bold {COLORS['thinking']}]Executing...")
    state.start_spinner()


def _handle_tool_result(
    data: dict,
    state: StreamingState,
    tool_name_by_id: dict[str, str],
) -> None:
    """Handle tool_call_result event."""
    agent = str(data.get("agent", ""))
    if "tools:" in agent:
        # Hide subagent/tool-node tool results in the CLI.
        return

    tool_call_id = data.get("tool_call_id")
    tool_name = tool_name_by_id.get(tool_call_id, "") if tool_call_id else ""

    status = data.get("status", "success")
    content = data.get("content", "")

    # Reset spinner
    if state.spinner_active:
        state.update_spinner(f"[bold {COLORS['thinking']}]Agent is thinking...")

    # Show errors
    if status != "success" and content:
        state.flush_text(final=True)
        if state.spinner_active:
            state.stop_spinner()
        console.print()
        console.print(truncate_error(str(content)), style="red", markup=False)
        console.print()
        return

    if tool_name in ("task", "wait", "task_output") and status == "success" and content:
        state.flush_text(final=True)
        if state.spinner_active:
            state.stop_spinner()

        icon = TOOL_ICONS.get(tool_name, "🔧")
        title = {
            "task": "Subagent result",
            "wait": "Subagent results",
            "task_output": "Task output",
        }.get(tool_name, f"{tool_name} result")

        if tool_call_id:
            title = f"{title} ({tool_call_id[:8]}...)"

        if isinstance(content, str):
            body = Markdown(content)
        else:
            body = Syntax(
                json.dumps(content, ensure_ascii=False, indent=2),
                "json",
                theme=get_syntax_theme(),
                line_numbers=False,
            )

        console.print()
        console.print(
            Panel(
                body,
                title=f"{icon} {title}",
                border_style=COLORS["tool"],
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )
        console.print()

        state.update_spinner(f"[bold {COLORS['thinking']}]Agent is thinking...")
        state.start_spinner()
