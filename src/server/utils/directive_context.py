"""
Directive context utilities for chat endpoint.

Parses DirectiveContext items from additional_context and builds
system-reminder strings for inline injection into user messages.
"""

import logging
from typing import Any, List, Optional

from src.server.models.additional_context import DirectiveContext

logger = logging.getLogger(__name__)


def parse_directive_contexts(
    additional_context: Optional[List[Any]],
) -> List[DirectiveContext]:
    """Extract DirectiveContext items from additional_context list.

    Args:
        additional_context: List of context items from ChatRequest

    Returns:
        List of DirectiveContext objects
    """
    if not additional_context:
        return []

    contexts = []

    for ctx in additional_context:
        if isinstance(ctx, dict):
            if ctx.get("type") == "directive":
                contexts.append(
                    DirectiveContext(
                        type="directive",
                        content=ctx.get("content", ""),
                    )
                )
        elif isinstance(ctx, DirectiveContext):
            contexts.append(ctx)
        elif hasattr(ctx, "type") and ctx.type == "directive":
            contexts.append(
                DirectiveContext(
                    type="directive",
                    content=getattr(ctx, "content", ""),
                )
            )

    return contexts


def build_directive_reminder(directives: List[DirectiveContext]) -> Optional[str]:
    """Build a system-reminder string from directive contexts.

    Args:
        directives: List of DirectiveContext objects

    Returns:
        Formatted ``<system-reminder>`` string, or None if no content
    """
    if not directives:
        return None

    parts = [d.content for d in directives if d.content]
    if not parts:
        return None

    return "\n\n<system-reminder>\n" + "\n".join(parts) + "\n</system-reminder>"
