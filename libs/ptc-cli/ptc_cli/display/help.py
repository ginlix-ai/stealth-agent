"""Help display utilities for the CLI."""

from rich.panel import Panel

from ptc_cli.core import COLORS, console


def show_help() -> None:
    """Show help information."""
    help_text = """
[bold]PTC Agent CLI[/bold] - Programmatic Tool Calling AI Assistant

[bold]Usage:[/bold]
  ptc-agent                     Start interactive session
  ptc-agent --agent NAME        Use named agent with separate memory
  ptc-agent --plan-mode         Enable plan mode (agent submits plan first)
  ptc-agent --reconnect         Reconnect to latest workflow
  ptc-agent --reconnect ID      Reconnect to specific workflow
  ptc-agent --list-sessions     List available reconnection sessions

[bold]Interactive Commands:[/bold]
  /help                         Show this help
  /clear                        Clear conversation and screen
  /tokens                       Show token usage
  /status                       Show workflow and background task status
  /cancel                       Cancel running workflow
  /reconnect                    Reconnect to running workflow after ESC
  /files [all]                  List files (all=include system dirs)
  /view <path>                  View file content (supports images)
  /copy <path>                  Copy file content to clipboard
  /download <path> [local]      Download file from sandbox
  /model                        Switch LLM model (only at session start)
  /exit, /q                     Exit the CLI

[bold]Special Input:[/bold]
  !command                      Run local bash command
  @path/to/file                 Include file content in prompt

[bold]Keyboard Shortcuts:[/bold]
  Enter                         Submit input
  Esc+Enter / Alt+Enter         Insert newline
  Ctrl+E                        Open in external editor
  Shift+Tab                     Toggle plan mode
  Esc (during streaming)        Soft-interrupt (background tasks continue)
  Ctrl+C                        Clear input / Interrupt / Exit (x3)

[bold]Configuration:[/bold]
  config.yaml                   Main configuration file
  llms.json                     LLM provider definitions
  .env                          API keys and credentials

[bold]Memory Files:[/bold] [dim](not yet active - agent runs in sandbox)[/dim]
  ~/.ptc-agent/{agent}/agent.md User-level agent memory
  .ptc-agent/agent.md           Project-level agent memory
"""

    console.print(Panel(help_text.strip(), title="Help", border_style=COLORS["primary"]))
    console.print()
