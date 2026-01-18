"""
Additional context models for workflow execution.

Supports flexible context types that can be passed along with user queries.
Contexts are fetched, formatted, and appended to user messages before processing.
"""

from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AdditionalContextBase(BaseModel):
    """Base model for additional context with type discrimination."""

    type: str = Field(..., description="Type of context (e.g., 'last_thread')")
    id: Optional[str] = Field(None, description="Resource identifier for fetching context")



class LastThreadContext(AdditionalContextBase):
    """Context referencing a previous thread for state restoration."""

    type: Literal["last_thread"] = "last_thread"
    id: str = Field(..., description="Thread ID of the previous thread to restore state from")


def format_additional_contexts(contexts: List[AdditionalContextBase]) -> str:
    """
    Format multiple additional contexts into a single markdown section.

    Args:
        contexts: List of formatted context strings

    Returns:
        Combined markdown section with separator
    """
    if not contexts:
        return ""

    return "\n\n---\n\n" + "\n\n".join(contexts)
