"""Tool call chunk buffering for streaming responses."""

import json
from typing import Any


class ToolCallChunkBuffer:
    """Buffers streaming tool call chunks until complete."""

    def __init__(self) -> None:
        """Initialize the tool call chunk buffer."""
        self._buffers: dict[str | int, dict[str, Any]] = {}
        self._displayed_ids: set[str] = set()

    def add_chunk(self, block: dict) -> dict | None:
        """Add a chunk. Returns complete tool call dict if ready, else None.

        Returns dict with keys: name, id, args (parsed dict)
        """
        chunk_name = block.get("name")
        chunk_args = block.get("args")
        chunk_id = block.get("id")
        chunk_index = block.get("index")

        # Determine buffer key
        if chunk_index is not None:
            buffer_key = chunk_index
        elif chunk_id is not None:
            buffer_key = chunk_id
        else:
            buffer_key = f"unknown-{len(self._buffers)}"

        buffer = self._buffers.setdefault(
            buffer_key,
            {"name": None, "id": None, "args": None, "args_parts": []},
        )

        if chunk_name:
            buffer["name"] = chunk_name
        if chunk_id:
            buffer["id"] = chunk_id

        # Handle args accumulation
        if isinstance(chunk_args, dict):
            buffer["args"] = chunk_args
            buffer["args_parts"] = []
        elif isinstance(chunk_args, str) and chunk_args:
            parts = buffer.setdefault("args_parts", [])
            if not parts or chunk_args != parts[-1]:
                parts.append(chunk_args)
            buffer["args"] = "".join(parts)
        elif chunk_args is not None:
            buffer["args"] = chunk_args

        # Check if complete
        if buffer.get("name") is None:
            return None

        parsed_args = buffer.get("args")
        if isinstance(parsed_args, str):
            if not parsed_args:
                return None
            try:
                parsed_args = json.loads(parsed_args)
            except json.JSONDecodeError:
                return None
        elif parsed_args is None:
            return None

        if not isinstance(parsed_args, dict):
            parsed_args = {"value": parsed_args}

        # Complete - clean up and return
        self._buffers.pop(buffer_key, None)
        return {
            "name": buffer["name"],
            "id": buffer["id"],
            "args": parsed_args,
        }

    def was_displayed(self, tool_id: str) -> bool:
        """Check if a tool call has already been displayed.

        Args:
            tool_id: The unique identifier of the tool call

        Returns:
            True if the tool call was already displayed, False otherwise
        """
        return tool_id in self._displayed_ids

    def mark_displayed(self, tool_id: str) -> None:
        """Mark a tool call as displayed.

        Args:
            tool_id: The unique identifier of the tool call to mark
        """
        self._displayed_ids.add(tool_id)
