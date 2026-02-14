"""
Memberships API Router.

Public endpoint — no auth required.
Frontend uses this to display available membership tiers.

Endpoints:
- GET /api/v1/memberships — List all memberships
"""

from fastapi import APIRouter

from src.server.services.membership_service import MembershipService

router = APIRouter(prefix="/api/v1/memberships", tags=["Memberships"])


@router.get("")
async def list_memberships():
    """Return all memberships ordered by rank."""
    svc = MembershipService.get_instance()
    await svc.ensure_loaded()
    memberships = svc.get_all_memberships()
    return {
        "memberships": [
            {
                "membership_id": m.membership_id,
                "name": m.name,
                "display_name": m.display_name,
                "rank": m.rank,
                "daily_credits": m.daily_credits,
                "max_active_workspaces": m.max_active_workspaces,
                "max_concurrent_requests": m.max_concurrent_requests,
            }
            for m in memberships
        ]
    }
