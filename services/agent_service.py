"""
Agent Service - Handles communication with PTC Agent server.

This service processes user input by sending it to the agent server
and accumulating the response from SSE events.
"""

import json
import os
from typing import Dict, Any, Optional
from urllib.parse import urljoin

import httpx


class AgentService:
    """Service for communicating with the PTC Agent server."""

    def __init__(self, server_url: Optional[str] = None):
        """Initialize the agent service.

        Args:
            server_url: PTC Agent server URL (default: http://localhost:8000)
        """
        self.server_url = (server_url or os.getenv("PTC_SERVER_URL", "http://localhost:8000")).rstrip("/")
        self.timeout = 600.0  # 10 minutes timeout for long-running tasks

    async def chat(
        self,
        message: str,
        workspace_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        plan_mode: bool = False,
        user_id: str = "api_user",
    ) -> Dict[str, Any]:
        """
        Send a message to the agent and get the response.

        This method:
        1. Sends the user input to the agent server
        2. Receives SSE (Server-Sent Events) stream
        3. Accumulates the response from message chunks
        4. Returns the complete response

        Args:
            message: User input message
            workspace_id: Optional workspace ID (creates new if not provided)
            thread_id: Optional thread ID (creates new if not provided)
            plan_mode: Whether to enable plan mode
            user_id: User identifier

        Returns:
            Dictionary with:
                - success: bool
                - message: str (accumulated agent response)
                - thread_id: str
                - workspace_id: Optional[str]
                - tool_calls: List[Dict] (tools used)
                - error: Optional[str]

        Raises:
            httpx.HTTPError: If server request fails
        """
        url = urljoin(self.server_url, "/api/v1/chat/stream")

        # Build request body (same format as CLI)
        request_body = {
            "user_id": user_id,
            "conversation_id": workspace_id or "default",
            "thread_id": thread_id or "__default__",
            "messages": [{"role": "user", "content": message}],
            "workspace_id": workspace_id,
            "track_tokens": True,
            "plan_mode": plan_mode,
        }

        # Accumulate response from SSE stream
        accumulated_message = ""
        tool_calls = []
        response_thread_id = thread_id or "__default__"
        response_workspace_id = workspace_id
        error_message = None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream(
                    "POST",
                    url,
                    json=request_body,
                    headers={"Accept": "text/event-stream"},
                ) as response:
                    response.raise_for_status()

                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk

                        # Parse complete SSE events (separated by \n\n)
                        while "\n\n" in buffer:
                            event_text, buffer = buffer.split("\n\n", 1)

                            # Parse SSE event
                            event_type = None
                            event_data = {}

                            for line in event_text.split("\n"):
                                line = line.strip()
                                if line.startswith("event: "):
                                    event_type = line[7:].strip()
                                elif line.startswith("data: "):
                                    try:
                                        event_data = json.loads(line[6:].strip())
                                    except json.JSONDecodeError:
                                        pass

                            # Handle different event types
                            if event_type == "message_chunk":
                                content = event_data.get("content", "")
                                content_type = event_data.get("content_type", "text")
                                
                                # Only accumulate regular text (not reasoning signals)
                                if content_type == "text" and content:
                                    accumulated_message += content
                                
                                # Track thread_id and workspace_id
                                if "thread_id" in event_data:
                                    response_thread_id = event_data["thread_id"]
                                if "workspace_id" in event_data:
                                    response_workspace_id = event_data.get("workspace_id")

                            elif event_type == "tool_calls":
                                # Accumulate tool calls
                                for tool_call in event_data.get("tool_calls", []):
                                    tool_calls.append({
                                        "name": tool_call.get("name"),
                                        "args": tool_call.get("args", {}),
                                        "id": tool_call.get("id"),
                                    })

                            elif event_type == "error":
                                error_message = event_data.get("error", "Unknown error")
                                break

                            elif event_type == "done":
                                # Workflow completed
                                break

                            # Ignore other event types (keepalive, tool_call_chunks, etc.)

            except httpx.HTTPStatusError as e:
                return {
                    "success": False,
                    "message": "",
                    "thread_id": response_thread_id,
                    "workspace_id": response_workspace_id,
                    "tool_calls": [],
                    "error": f"Server error: {e.response.status_code} - {e.response.text}",
                }
            except httpx.RequestError as e:
                return {
                    "success": False,
                    "message": "",
                    "thread_id": response_thread_id,
                    "workspace_id": response_workspace_id,
                    "tool_calls": [],
                    "error": f"Connection error: {str(e)}. Make sure the agent server is running on {self.server_url}",
                }
            except Exception as e:
                return {
                    "success": False,
                    "message": "",
                    "thread_id": response_thread_id,
                    "workspace_id": response_workspace_id,
                    "tool_calls": [],
                    "error": f"Unexpected error: {str(e)}",
                }

        # Return accumulated response
        if error_message:
            return {
                "success": False,
                "message": accumulated_message,
                "thread_id": response_thread_id,
                "workspace_id": response_workspace_id,
                "tool_calls": tool_calls,
                "error": error_message,
            }

        return {
            "success": True,
            "message": accumulated_message,
            "thread_id": response_thread_id,
            "workspace_id": response_workspace_id,
            "tool_calls": tool_calls,
            "error": None,
        }
