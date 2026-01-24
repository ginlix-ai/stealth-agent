"""
SSE Stream Client for ptc-cli
==============================

HTTP/SSE client for communicating with the PTC Agent server API.
Adapted from tui/client.py for CLI context.
"""

import json
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from rich.console import Console

from ptc_cli.api.constants import DEFAULT_BASE_URL, DEFAULT_TIMEOUT
from ptc_cli.api.models import Message

console = Console()


class SSEStreamClient:
    """
    Client for SSE streaming from PTC Agent server.

    Handles:
    - Workspace management (list, create, start, stop)
    - Chat streaming via SSE
    - Workflow control (cancel)
    - Reconnection with event ID tracking
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        user_id: str = "cli_user",
        timeout: float = DEFAULT_TIMEOUT,
    ):
        """
        Initialize the SSE stream client.

        Args:
            base_url: Server base URL
            user_id: User identifier for requests
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.user_id = user_id
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

        # Session state
        self.workspace_id: Optional[str] = None
        self.thread_id: Optional[str] = None
        self.last_event_id: int = 0

        # Message accumulation
        self.current_message: Message = Message()
        self.last_plan_data: Optional[Dict[str, Any]] = None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self) -> "SSEStreamClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    # =========================================================================
    # Workspace Management
    # =========================================================================

    async def list_workspaces(self) -> List[Dict[str, Any]]:
        """
        List available workspaces for the current user.

        Returns:
            List of workspace dicts with id, name, status, etc.
        """
        url = urljoin(self.base_url, "/api/v1/workspaces")
        response = await self.client.get(
            url,
            headers={"X-User-Id": self.user_id},
        )
        response.raise_for_status()
        return response.json().get("workspaces", [])

    async def create_workspace(self, name: str) -> Dict[str, Any]:
        """
        Create a new workspace with dedicated sandbox.

        Args:
            name: Workspace name

        Returns:
            Created workspace dict with id, sandbox_id, etc.

        Note: Workspace creation takes 60+ seconds due to sandbox provisioning.
        """
        url = urljoin(self.base_url, "/api/v1/workspaces")
        response = await self.client.post(
            url,
            headers={"X-User-Id": self.user_id},
            json={"name": name},
            timeout=120.0,  # Extended timeout for sandbox creation
        )
        response.raise_for_status()
        return response.json()

    async def get_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """
        Get workspace details by ID.

        Args:
            workspace_id: Workspace identifier

        Returns:
            Workspace dict or None if not found
        """
        url = urljoin(self.base_url, f"/api/v1/workspaces/{workspace_id}")
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def start_workspace(self, workspace_id: str) -> Dict[str, Any]:
        """
        Start a stopped workspace.

        Args:
            workspace_id: Workspace identifier

        Returns:
            Updated workspace dict
        """
        url = urljoin(self.base_url, f"/api/v1/workspaces/{workspace_id}/start")
        response = await self.client.post(url, timeout=30.0)
        response.raise_for_status()
        return response.json()

    async def stop_workspace(self, workspace_id: str) -> Dict[str, Any]:
        """
        Stop a running workspace (keeps sandbox for later).

        Args:
            workspace_id: Workspace identifier

        Returns:
            Updated workspace dict
        """
        url = urljoin(self.base_url, f"/api/v1/workspaces/{workspace_id}/stop")
        response = await self.client.post(url, timeout=30.0)
        response.raise_for_status()
        return response.json()

    async def delete_workspace(self, workspace_id: str) -> Dict[str, Any]:
        """
        Delete a workspace and its sandbox.

        Args:
            workspace_id: Workspace identifier

        Returns:
            Deletion confirmation dict
        """
        url = urljoin(self.base_url, f"/api/v1/workspaces/{workspace_id}")
        response = await self.client.delete(url, timeout=30.0)
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # Workspace Refresh
    # =========================================================================

    async def refresh_workspace(self) -> dict[str, Any]:
        """Rebuild sandbox tool modules and sync skills."""
        if not self.workspace_id:
            raise ValueError("workspace_id is required. Create a workspace first via POST /workspaces")

        url = urljoin(self.base_url, f"/api/v1/workspaces/{self.workspace_id}/refresh")
        response = await self.client.post(
            url,
            headers={"X-User-Id": self.user_id},
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # Workspace Files (Live Sandbox)
    # =========================================================================

    async def list_workspace_files(
        self,
        *,
        path: str = ".",
        include_system: bool = False,
        pattern: str = "**/*",
    ) -> list[str]:
        """List files in the active workspace sandbox."""
        if not self.workspace_id:
            raise ValueError("workspace_id is required. Create a workspace first via POST /workspaces")

        url = urljoin(self.base_url, f"/api/v1/workspaces/{self.workspace_id}/files")
        response = await self.client.get(
            url,
            headers={"X-User-Id": self.user_id},
            params={"path": path, "include_system": include_system, "pattern": pattern},
        )
        response.raise_for_status()
        return list(response.json().get("files", []) or [])

    async def read_workspace_file(
        self,
        *,
        path: str,
        offset: int = 0,
        limit: int = 20000,
    ) -> dict[str, Any]:
        """Read a file from the active workspace sandbox."""
        if not self.workspace_id:
            raise ValueError("workspace_id is required. Create a workspace first via POST /workspaces")

        url = urljoin(self.base_url, f"/api/v1/workspaces/{self.workspace_id}/files/read")
        response = await self.client.get(
            url,
            headers={"X-User-Id": self.user_id},
            params={"path": path, "offset": offset, "limit": limit},
        )
        response.raise_for_status()
        return response.json()

    async def download_workspace_file(self, *, path: str) -> bytes:
        """Download raw bytes from the active workspace sandbox."""
        if not self.workspace_id:
            raise ValueError("workspace_id is required. Create a workspace first via POST /workspaces")

        url = urljoin(self.base_url, f"/api/v1/workspaces/{self.workspace_id}/files/download")
        response = await self.client.get(
            url,
            headers={"X-User-Id": self.user_id},
            params={"path": path},
        )
        response.raise_for_status()
        return response.content

    async def upload_workspace_file(
        self,
        *,
        path: str,
        content: bytes,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """Upload bytes to a file in the active workspace sandbox."""
        if not self.workspace_id:
            raise ValueError("workspace_id is required. Create a workspace first via POST /workspaces")

        url = urljoin(self.base_url, f"/api/v1/workspaces/{self.workspace_id}/files/upload")
        files = {"file": (filename or path.split("/")[-1] or "upload", content)}
        response = await self.client.post(
            url,
            headers={"X-User-Id": self.user_id},
            params={"path": path},
            files=files,
        )
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # Conversations
    # =========================================================================

    async def list_conversations(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        """List conversations (threads) for the current user."""
        url = urljoin(self.base_url, "/api/v1/conversations")
        response = await self.client.get(
            url,
            headers={"X-User-Id": self.user_id},
            params={
                "limit": limit,
                "offset": offset,
                "sort_by": sort_by,
                "sort_order": sort_order,
            },
        )
        response.raise_for_status()
        return response.json()

    async def replay_thread(self, thread_id: str) -> AsyncGenerator[tuple[str, Dict[str, Any]], None]:
        """Replay a completed thread from persisted streaming chunks."""
        url = urljoin(self.base_url, f"/api/v1/threads/{thread_id}/replay")

        async with self.client.stream(
            "GET",
            url,
            headers={"Accept": "text/event-stream"},
            timeout=self.timeout,
        ) as response:
            response.raise_for_status()

            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk

                while "\n\n" in buffer:
                    event_text, buffer = buffer.split("\n\n", 1)

                    if parsed := self._parse_sse_event(event_text):
                        event_type, event_data = parsed
                        # Track thread_id from events
                        if "thread_id" in event_data:
                            self.thread_id = event_data["thread_id"]
                        yield event_type, event_data

    # =========================================================================
    # Chat Streaming
    # =========================================================================

    async def stream_chat(
        self,
        message: str,
        thread_id: Optional[str] = None,
        hitl_response: Optional[Dict[str, Any]] = None,
        plan_mode: bool = False,
        llm_model: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[tuple[str, Dict[str, Any]], None]:
        """
        Stream chat responses via SSE.

        Args:
            message: User message (can be empty for resume)
            thread_id: Thread identifier for conversation continuity
            hitl_response: HITL interrupt response (for resume)
            plan_mode: Whether to enable plan mode (agent submits plan for approval)
            llm_model: LLM model name from models.json (e.g., 'minimax-m2.1')
            **kwargs: Additional request parameters

        Yields:
            Tuples of (event_type, event_data)
        """
        url = urljoin(self.base_url, "/api/v1/chat/stream")

        # Build request body (workspace_id is required)
        if not self.workspace_id:
            raise ValueError("workspace_id is required. Create a workspace first via POST /workspaces")

        request_body = {
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "thread_id": thread_id or self.thread_id or "__default__",
            "messages": [{"role": "user", "content": message}] if message else [],
            "track_tokens": True,
            "plan_mode": plan_mode,
        }

        # Add LLM model if specified
        if llm_model:
            request_body["llm_model"] = llm_model

        # Add HITL response for resume
        if hitl_response:
            request_body["hitl_response"] = hitl_response

        # Add any additional parameters
        request_body.update(kwargs)

        # Reset message state for new stream
        self.current_message = Message()

        async with self.client.stream(
            "POST",
            url,
            json=request_body,
            headers={"Accept": "text/event-stream"},
            timeout=self.timeout,
        ) as response:
            response.raise_for_status()

            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk

                # Parse complete SSE events (separated by \n\n)
                while "\n\n" in buffer:
                    event_text, buffer = buffer.split("\n\n", 1)

                    if parsed := self._parse_sse_event(event_text):
                        event_type, event_data = parsed

                        # Update internal state
                        self._update_state(event_type, event_data)

                        yield event_type, event_data

    async def reconnect_to_stream(
        self,
        thread_id: str,
        last_event_id: Optional[int] = None,
    ) -> AsyncGenerator[tuple[str, Dict[str, Any]], None]:
        """
        Reconnect to an existing workflow stream.

        Args:
            thread_id: Thread identifier to reconnect to
            last_event_id: Last received event ID for replay

        Yields:
            Tuples of (event_type, event_data)
        """
        url = urljoin(self.base_url, f"/api/v1/chat/stream/{thread_id}/reconnect")

        params = {}
        if last_event_id is not None:
            params["last_event_id"] = last_event_id

        # Reset message state
        self.current_message = Message()
        self.thread_id = thread_id

        async with self.client.stream(
            "GET",
            url,
            params=params,
            headers={"Accept": "text/event-stream"},
            timeout=self.timeout,
        ) as response:
            response.raise_for_status()

            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk

                while "\n\n" in buffer:
                    event_text, buffer = buffer.split("\n\n", 1)

                    if parsed := self._parse_sse_event(event_text):
                        event_type, event_data = parsed
                        self._update_state(event_type, event_data)
                        yield event_type, event_data

    async def stream_subagent_status(
        self,
        thread_id: str,
    ) -> AsyncGenerator[tuple[str, Dict[str, Any]], None]:
        """Stream subagent status updates for a thread."""
        url = urljoin(self.base_url, f"/api/v1/chat/stream/{thread_id}/status")

        async with self.client.stream(
            "GET",
            url,
            headers={"Accept": "text/event-stream"},
            timeout=self.timeout,
        ) as response:
            response.raise_for_status()

            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk

                while "\n\n" in buffer:
                    event_text, buffer = buffer.split("\n\n", 1)

                    if parsed := self._parse_sse_event(event_text):
                        event_type, event_data = parsed
                        if "thread_id" in event_data:
                            self.thread_id = event_data["thread_id"]
                        yield event_type, event_data

    # =========================================================================
    # Workflow Control
    # =========================================================================

    async def cancel_workflow(self, thread_id: str) -> Dict[str, Any]:
        """
        Cancel a running workflow.

        Args:
            thread_id: Thread identifier

        Returns:
            Cancellation confirmation dict
        """
        url = urljoin(self.base_url, f"/api/v1/workflow/{thread_id}/cancel")
        response = await self.client.post(url)
        response.raise_for_status()
        return response.json()

    async def soft_interrupt(self, thread_id: str) -> Dict[str, Any]:
        """
        Soft interrupt - pause main agent, keep subagents running.

        Unlike cancel_workflow() which stops everything, soft interrupt:
        - Pauses the main agent stream
        - Allows background subagents to continue execution
        - Enables resumption with new input

        Args:
            thread_id: Thread identifier

        Returns:
            Dict with status, can_resume, and background_tasks info
        """
        url = urljoin(self.base_url, f"/api/v1/workflow/{thread_id}/soft-interrupt")
        response = await self.client.post(url)
        response.raise_for_status()
        return response.json()

    async def get_workflow_status(self, thread_id: str) -> Dict[str, Any]:
        """
        Get workflow status.

        Args:
            thread_id: Thread identifier

        Returns:
            Status dict with state, started_at, etc.
        """
        url = urljoin(self.base_url, f"/api/v1/workflow/{thread_id}/status")
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _parse_sse_event(self, event_text: str) -> Optional[tuple[str, Dict[str, Any]]]:
        """
        Parse SSE event text into (event_type, data) tuple.

        SSE format:
            id: 123
            event: message_chunk
            data: {"content": "hello"}

        Args:
            event_text: Raw SSE event text

        Returns:
            Tuple of (event_type, data) or None if invalid
        """
        if not event_text.strip():
            return None

        event_type = None
        event_data: Dict[str, Any] = {}

        for line in event_text.split("\n"):
            line = line.strip()

            if line.startswith("id: "):
                try:
                    self.last_event_id = int(line[4:].strip())
                except ValueError:
                    pass

            elif line.startswith("event: "):
                event_type = line[7:].strip()

            elif line.startswith("data: "):
                try:
                    event_data = json.loads(line[6:].strip())
                except json.JSONDecodeError:
                    event_data = {"raw": line[6:].strip()}

        if event_type and event_data:
            return event_type, event_data

        return None

    def _update_state(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Update internal state based on event.

        Args:
            event_type: SSE event type
            event_data: Event payload
        """
        # Track thread_id from events
        if "thread_id" in event_data:
            self.thread_id = event_data["thread_id"]

        # Accumulate message chunks
        self.current_message.merge_event(event_type, event_data)

        # Capture plan data
        if self.current_message.plan_data:
            self.last_plan_data = self.current_message.plan_data
