"""Interactive menu utilities using prompt_toolkit."""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl

T = TypeVar("T")


async def create_interactive_menu(
    options: list[tuple[str, T]],
    title: str = "Select an option",
    *,
    cancel_text: str = "(Ctrl+C to cancel)",
    extra_bindings: dict[str, Callable[[Any], tuple[str, int] | None]] | None = None,
    status_line: str | None = None,
) -> tuple[int, T] | None:
    """Create an interactive menu with keyboard navigation.

    Args:
        options: List of (label, value) tuples for menu items
        title: Title displayed at the top of the menu
        cancel_text: Text shown for cancel instruction
        extra_bindings: Optional dict of key -> handler for additional bindings.
                        Handler receives event and returns (action, index) or None.
        status_line: Optional status line shown below title (e.g., keybinding hints)

    Returns:
        Tuple of (selected_index, selected_value) or None if cancelled
    """
    if not options:
        return None

    selected = [0]

    def menu_text() -> str:
        lines = [title]
        if status_line:
            lines.append(status_line)
        lines.append("")
        for idx, (label, _value) in enumerate(options):
            prefix = ">" if idx == selected[0] else " "
            lines.append(f" {prefix} {idx + 1}. {label}")
        lines.append("")
        lines.append(cancel_text)
        return "\n".join(lines)

    kb = KeyBindings()

    @kb.add("up")
    def _up(_event: Any) -> None:
        selected[0] = max(0, selected[0] - 1)

    @kb.add("down")
    def _down(_event: Any) -> None:
        selected[0] = min(len(options) - 1, selected[0] + 1)

    @kb.add("enter")
    def _enter(event: Any) -> None:
        event.app.exit(result=("select", selected[0]))

    @kb.add("c-c")
    def _cancel(event: Any) -> None:
        event.app.exit(result=("cancel", -1))

    # Add extra bindings if provided
    if extra_bindings:
        for key, handler in extra_bindings.items():

            @kb.add(key)
            def _handler(event: Any, h: Callable = handler) -> None:
                result = h(event)
                if result is not None:
                    event.app.exit(result=result)

    app: Application[tuple[str, int]] = Application(
        layout=Layout(Window(FormattedTextControl(menu_text))),
        key_bindings=kb,
        full_screen=False,
    )

    action, index = await app.run_async()
    if action == "cancel":
        return None

    return (index, options[index][1])
