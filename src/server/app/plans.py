"""
Plans API Router.

Public endpoint — no auth required.
Frontend uses this to display available plans.

Endpoints:
- GET /api/v1/plans — List all plans
"""

from fastapi import APIRouter

from src.server.services.plan_service import PlanService

router = APIRouter(prefix="/api/v1/plans", tags=["Plans"])


@router.get("")
async def list_plans():
    """Return all plans ordered by rank."""
    svc = PlanService.get_instance()
    await svc.ensure_loaded()
    plans = svc.get_all_plans()
    return {
        "plans": [
            {
                "id": p.id,
                "name": p.name,
                "display_name": p.display_name,
                "rank": p.rank,
                "daily_credits": p.daily_credits,
                "max_active_workspaces": p.max_active_workspaces,
                "max_concurrent_requests": p.max_concurrent_requests,
            }
            for p in plans
        ]
    }
