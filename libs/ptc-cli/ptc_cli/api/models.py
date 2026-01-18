"""
Data Models for API Client Module
===================================

Contains the Message class for accumulating streaming chunks and managing
message state during SSE streaming.
"""

import json
from typing import Any, Dict, List, Optional

from rich.console import Console

console = Console()


class Message:
    """
    Represents a message being accumulated from SSE chunks.
    Mirrors the frontend's message state management.
    """

    def __init__(self):
        self.id: Optional[str] = None
        self.agent: Optional[str] = None
        self.role: str = "assistant"
        self.content: str = ""
        self.content_chunks: List[str] = []
        self.content_type: str = "text"  # "text" or "reasoning"
        self.tool_calls: List[Dict[str, Any]] = []
        self.is_streaming: bool = True
        self.is_thinking: bool = False  # Track if agent is actively thinking
        self.finish_reason: Optional[str] = None
        self.options: List[Dict[str, str]] = []
        self.plan_data: Optional[Dict[str, Any]] = None  # Store plan from create_plan tool

    def merge_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Merge an SSE event into the message state.
        This mimics the frontend's mergeMessage function.
        """
        handlers = {
            "message_chunk": self._handle_message_chunk,
            "tool_calls": self._handle_tool_calls,
            "tool_call_chunks": self._handle_tool_call_chunks,
            "tool_call_result": self._handle_tool_call_result,
            "interrupt": self._handle_interrupt,
        }

        if handler := handlers.get(event_type):
            handler(event_data)

    def _handle_message_chunk(self, data: Dict[str, Any]) -> None:
        """
        Handle message_chunk event - accumulates content.

        Server normalizes content and provides semantic content_type:
        - content_type="reasoning_signal": Lifecycle events (content="start" or "complete")
        - content_type="text": Regular text content (plain string)
        - content_type="reasoning": Reasoning/thinking content (plain string, unified from all providers)

        Note: Server already normalizes all content. Content field is always a plain string.
        """
        self.id = data.get("id", self.id)
        self.agent = data.get("agent", self.agent)
        self.content_type = data.get("content_type", "text")

        # Handle reasoning signal (lifecycle events)
        if self.content_type == "reasoning_signal":
            signal_content = data.get("content", "")
            if signal_content == "start":
                self.is_thinking = True
            elif signal_content == "complete":
                self.is_thinking = False
            # Don't accumulate signal content
            return

        # Process main text content (already normalized by server as plain string)
        if content := data.get("content"):
            self.content += content
            self.content_chunks.append(content)

        # Check if streaming is finished
        if finish := data.get("finish_reason"):
            self.finish_reason = finish
            self.is_streaming = False

    def _handle_tool_calls(self, data: Dict[str, Any]) -> None:
        """
        Handle tool_calls event - new tool invocations.

        Server already sends complete, parsed args as dict.
        No client-side parsing needed.
        """
        self.agent = data.get("agent", self.agent)
        if tool_calls := data.get("tool_calls"):
            self.tool_calls = [
                {
                    "id": tc.get("id"),
                    "name": tc.get("name"),
                    "args": tc.get("args", {}),  # Already complete dict from server
                    "result": None,
                }
                for tc in tool_calls
            ]

    def _handle_tool_call_chunks(self, data: Dict[str, Any]) -> None:
        """
        Handle tool_call_chunks event - streaming tool arguments.

        Server sends complete args in tool_calls event, so no accumulation needed.
        Chunks are displayed for animation only.
        """
        # No action needed - args are already complete from tool_calls event
        pass

    def _handle_tool_call_result(self, data: Dict[str, Any]) -> None:
        """Handle tool_call_result event - tool execution results."""
        tool_call_id = data.get("tool_call_id")
        if tool_call := self._find_tool_call(tool_call_id):
            tool_call["result"] = data.get("content")

            # Capture plan data from create_plan tool
            if tool_call.get("name") == "create_plan":
                content = data.get("content")
                if content:
                    try:
                        # Parse plan JSON from tool result
                        parsed_content = None
                        if isinstance(content, str):
                            parsed_content = json.loads(content)
                        elif isinstance(content, dict):
                            parsed_content = content

                        # Check for new structure with status and plan fields
                        if parsed_content and isinstance(parsed_content, dict):
                            status = parsed_content.get("status")
                            if status == "success":
                                # Extract plan from the plan field
                                if "plan" in parsed_content:
                                    self.plan_data = parsed_content["plan"]
                                    console.print(
                                        "\n[dim cyan]Plan captured from create_plan tool[/dim cyan]"
                                    )
                            else:
                                # Handle non-success status
                                error_msg = parsed_content.get("error", "Unknown error")
                                console.print(
                                    f"\n[dim red]Plan creation failed: {error_msg}[/dim red]"
                                )
                    except json.JSONDecodeError:
                        console.print(
                            "\n[dim yellow]Failed to parse plan from create_plan tool[/dim yellow]"
                        )

    def _handle_interrupt(self, data: Dict[str, Any]) -> None:
        """Handle interrupt event - user interaction required."""
        self.is_streaming = False
        self.finish_reason = "interrupt"
        self.options = data.get("options", [])

    def _find_tool_call(self, tool_call_id: str) -> Optional[Dict[str, Any]]:
        """Find a tool call by ID."""
        for tc in self.tool_calls:
            if tc["id"] == tool_call_id:
                return tc
        return None

    def finalize(self) -> None:
        """
        Finalize the message after streaming completes.

        Server already sends complete parsed args, so no parsing needed.
        """
        self.is_streaming = False
