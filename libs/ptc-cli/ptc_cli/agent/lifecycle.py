"""API session lifecycle functions for the CLI."""

from collections.abc import Callable

import structlog

from ptc_cli.agent.persistence import (
    delete_persisted_session,
    load_persisted_session,
    save_persisted_session,
    update_session_last_used,
)
from ptc_cli.api.client import SSEStreamClient

logger = structlog.get_logger(__name__)


async def create_api_session(
    agent_name: str,
    server_url: str = "http://localhost:8000",
    workspace_id: str | None = None,
    *,
    persist_session: bool = True,
    on_progress: Callable[[str], None] | None = None,
) -> tuple[SSEStreamClient, str, bool]:
    """Create API session with workspace.

    Args:
        agent_name: Agent identifier for session storage
        server_url: PTC Agent server URL
        workspace_id: Optional existing workspace ID to reuse (overrides persistence)
        persist_session: Whether to persist/reuse workspace sessions
        on_progress: Optional callback for progress updates

    Returns:
        Tuple of (client, workspace_id, reusing_workspace)
    """
    def report(step: str) -> None:
        if on_progress:
            on_progress(step)

    client = SSEStreamClient(base_url=server_url, user_id=agent_name)
    reusing_workspace = False

    try:
        if workspace_id:
            # Explicit workspace_id provided via CLI - use it directly
            report("Connecting to workspace...")
            workspace = await client.get_workspace(workspace_id)
            if workspace:
                if workspace.get("status") == "stopped":
                    report("Starting workspace...")
                    await client.start_workspace(workspace_id)
                reusing_workspace = True
                client.workspace_id = workspace_id
            else:
                raise ValueError(f"Workspace {workspace_id} not found")

        elif persist_session:
            # Check for persisted session
            persisted = load_persisted_session(agent_name)
            if persisted and persisted.get("workspace_id"):
                persisted_workspace_id = persisted["workspace_id"]
                report("Reconnecting to workspace...")
                try:
                    workspace = await client.get_workspace(persisted_workspace_id)
                    if workspace:
                        if workspace.get("status") == "stopped":
                            report("Starting workspace...")
                            await client.start_workspace(persisted_workspace_id)
                        workspace_id = persisted_workspace_id
                        reusing_workspace = True
                        client.workspace_id = workspace_id
                        update_session_last_used(agent_name)
                    else:
                        # Workspace not found, delete persisted session
                        delete_persisted_session(agent_name)
                except Exception:  # noqa: BLE001
                    # Reconnection failed, delete persisted session
                    report("Workspace reconnection failed...")
                    delete_persisted_session(agent_name)

        # Create new workspace if needed
        if not workspace_id:
            report("Creating workspace...")
            workspace = await client.create_workspace(name=f"cli-{agent_name}")
            workspace_id = workspace["workspace_id"]
            client.workspace_id = workspace_id

            if persist_session:
                save_persisted_session(agent_name, workspace_id)

        return client, workspace_id, reusing_workspace

    except Exception:
        # Clean up client on error
        await client.close()
        raise
