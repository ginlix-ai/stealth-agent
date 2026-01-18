"""Token tracking utilities for the CLI."""

from rich import box
from rich.table import Table

from ptc_cli.core import console


class TokenTracker:
    """Track token usage across a session."""

    def __init__(self) -> None:
        """Initialize the token tracker."""
        self.input_tokens = 0
        self.output_tokens = 0
        self.baseline_tokens = 0

    def set_baseline(self, tokens: int) -> None:
        """Set baseline token count (system prompt, etc)."""
        self.baseline_tokens = tokens

    def add(self, input_tokens: int, output_tokens: int) -> None:
        """Add token counts from a request."""
        self.input_tokens = max(self.input_tokens, input_tokens)
        self.output_tokens = max(self.output_tokens, output_tokens)

    @property
    def total(self) -> int:
        """Get total tokens used."""
        return self.input_tokens + self.output_tokens

    def display(self) -> None:
        """Display token usage to console."""
        table = Table(title="Token Usage", box=box.ROUNDED)
        table.add_column("Category", style="cyan")
        table.add_column("Count", justify="right", style="green")

        table.add_row("Input tokens", str(self.input_tokens))
        table.add_row("Output tokens", str(self.output_tokens))
        table.add_row("Total", str(self.total))

        if self.baseline_tokens:
            table.add_row("Baseline (system)", str(self.baseline_tokens))

        console.print()
        console.print(table)
        console.print()
