"""
Sessions endpoint — active session stats.

Moved from /api/v1/chat/sessions to /api/v1/sessions.
"""

from fastapi import APIRouter

from src.server.services.session_manager import SessionService

router = APIRouter(prefix="/api/v1/sessions", tags=["Sessions"])


@router.get("")
async def get_sessions():
    """
    Get information about active PTC sessions.

    Returns:
        Dict with session statistics and details
    """
    try:
        session_service = SessionService.get_instance()
        return session_service.get_stats()
    except ValueError:
        # Service not initialized
        return {
            "active_sessions": 0,
            "message": "PTC Session Service not initialized",
        }
