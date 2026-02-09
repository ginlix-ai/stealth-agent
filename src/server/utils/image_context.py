"""
Image context utilities for chat endpoint.

Parses ImageContext items from additional_context and injects image content
blocks into user messages so the LLM receives both text and images.
"""

import logging
from typing import Any, Dict, List, Optional

from src.server.models.additional_context import ImageContext

logger = logging.getLogger(__name__)


def parse_image_contexts(
    additional_context: Optional[List[Any]],
) -> List[ImageContext]:
    """Extract ImageContext items from additional_context list.

    Args:
        additional_context: List of context items from ChatRequest

    Returns:
        List of ImageContext objects
    """
    if not additional_context:
        return []

    image_contexts = []

    for ctx in additional_context:
        if isinstance(ctx, dict):
            if ctx.get("type") == "image":
                image_contexts.append(
                    ImageContext(
                        type="image",
                        data=ctx.get("data", ""),
                        description=ctx.get("description"),
                    )
                )
        elif isinstance(ctx, ImageContext):
            image_contexts.append(ctx)
        elif hasattr(ctx, "type") and ctx.type == "image":
            image_contexts.append(
                ImageContext(
                    type="image",
                    data=getattr(ctx, "data", ""),
                    description=getattr(ctx, "description", None),
                )
            )

    return image_contexts


def inject_image_context(
    messages: List[Dict[str, Any]],
    image_contexts: List[ImageContext],
) -> List[Dict[str, Any]]:
    """Inject a separate context message with chart image before the user query.

    Inserts a new user message containing the description + image(s) right
    before the last user message, so the LLM sees the visual context first
    and the user's question second.

    Args:
        messages: List of message dicts (role + content)
        image_contexts: List of ImageContext objects to inject

    Returns:
        Modified messages list with context message inserted
    """
    if not image_contexts or not messages:
        return messages

    # Build the context message content blocks
    blocks: List[Dict[str, Any]] = []
    for img_ctx in image_contexts:
        if img_ctx.description:
            blocks.append({
                "type": "text",
                "text": f"[Attached chart screenshot]\n{img_ctx.description}",
            })
        blocks.append({"type": "image_url", "image_url": img_ctx.data})

    if not blocks:
        return messages

    context_message = {"role": "user", "content": blocks}

    # Insert before the last user message
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            messages.insert(i, context_message)
            break

    return messages
