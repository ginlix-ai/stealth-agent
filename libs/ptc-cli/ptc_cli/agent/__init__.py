"""Agent module for the PTC CLI (API mode)."""

from ptc_cli.agent.lifecycle import create_api_session
from ptc_cli.agent.persistence import (
    SESSION_MAX_AGE_HOURS,
    delete_persisted_session,
    load_persisted_session,
    save_persisted_session,
    update_session_last_used,
)

__all__ = [
    "SESSION_MAX_AGE_HOURS",
    "create_api_session",
    "delete_persisted_session",
    "load_persisted_session",
    "save_persisted_session",
    "update_session_last_used",
]
