"""Session persistence functions for the CLI (API mode)."""

import contextlib
import json
from datetime import UTC, datetime

from ptc_cli.core import settings

# Maximum age for a persisted session (24 hours)
SESSION_MAX_AGE_HOURS = 24


def load_persisted_session(agent_name: str) -> dict | None:
    """Load persisted session data for an agent.

    Args:
        agent_name: Name of the agent

    Returns:
        Session data dict or None if not found/invalid
    """
    session_file = settings.get_session_file_path(agent_name)
    if not session_file.exists():
        return None

    try:
        data = json.loads(session_file.read_text())

        # Validate required fields
        if not data.get("workspace_id"):
            return None

        # Check session age
        if "last_used" in data:
            last_used = datetime.fromisoformat(data["last_used"])
            # Handle old sessions that may have naive datetimes (assume UTC)
            if last_used.tzinfo is None:
                last_used = last_used.replace(tzinfo=UTC)
            age_hours = (datetime.now(tz=UTC) - last_used).total_seconds() / 3600
            if age_hours > SESSION_MAX_AGE_HOURS:
                # Session too old, delete it
                session_file.unlink()
                return None
    except (json.JSONDecodeError, ValueError, KeyError):
        # Invalid session file, delete it
        with contextlib.suppress(Exception):
            session_file.unlink()
        return None
    else:
        return data


def save_persisted_session(agent_name: str, workspace_id: str) -> None:
    """Save session data for persistence.

    Args:
        agent_name: Name of the agent
        workspace_id: Workspace ID from server
    """
    settings.ensure_agent_dir(agent_name)
    session_file = settings.get_session_file_path(agent_name)

    data = {
        "workspace_id": workspace_id,
        "created_at": datetime.now(tz=UTC).isoformat(),
        "last_used": datetime.now(tz=UTC).isoformat(),
    }

    session_file.write_text(json.dumps(data, indent=2))


def update_session_last_used(agent_name: str) -> None:
    """Update the last_used timestamp of a persisted session.

    Args:
        agent_name: Name of the agent
    """
    session_file = settings.get_session_file_path(agent_name)
    if not session_file.exists():
        return

    try:
        data = json.loads(session_file.read_text())
        data["last_used"] = datetime.now(tz=UTC).isoformat()
        session_file.write_text(json.dumps(data, indent=2))
    except Exception:  # noqa: BLE001, S110
        # Silently ignore errors when updating timestamp
        pass


def delete_persisted_session(agent_name: str) -> None:
    """Delete persisted session data.

    Args:
        agent_name: Name of the agent
    """
    session_file = settings.get_session_file_path(agent_name)
    try:
        if session_file.exists():
            session_file.unlink()
    except Exception:  # noqa: BLE001, S110
        # Silently ignore errors when deleting session files
        pass
