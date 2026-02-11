"""
PlanService — singleton that caches plan definitions from the `plans` DB table.

Usage:
    svc = PlanService.get_instance()
    await svc.ensure_loaded()       # async — call once (or periodically)
    plan = svc.get_plan(plan_id)    # sync dict lookup after that
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.config.settings import get_usage_limits_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlanInfo:
    id: int
    name: str
    display_name: str
    rank: int
    daily_credits: float
    max_active_workspaces: int
    max_concurrent_requests: int
    is_default: bool


# Hardcoded fallback if DB is unreachable on first boot
_FALLBACK_PLAN = PlanInfo(
    id=1,
    name="free",
    display_name="Free",
    rank=0,
    daily_credits=50.0,
    max_active_workspaces=3,
    max_concurrent_requests=5,
    is_default=True,
)


class PlanService:
    _instance: Optional["PlanService"] = None

    def __init__(self) -> None:
        self._plans_by_id: Dict[int, PlanInfo] = {}
        self._plans_by_name: Dict[str, PlanInfo] = {}
        self._default_plan: Optional[PlanInfo] = None
        self._loaded_at: float = 0.0

    # ── singleton ────────────────────────────────────────────────
    @classmethod
    def get_instance(cls) -> "PlanService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── async DB loading ─────────────────────────────────────────
    async def refresh(self) -> None:
        """Load all plans from DB into memory."""
        try:
            from src.server.database.conversation import get_db_connection
            from psycopg.rows import dict_row

            async with get_db_connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        "SELECT id, name, display_name, rank, daily_credits, "
                        "max_active_workspaces, max_concurrent_requests, is_default "
                        "FROM plans ORDER BY rank"
                    )
                    rows = await cur.fetchall()

            by_id: Dict[int, PlanInfo] = {}
            by_name: Dict[str, PlanInfo] = {}
            default: Optional[PlanInfo] = None

            for row in rows:
                plan = PlanInfo(
                    id=row["id"],
                    name=row["name"],
                    display_name=row["display_name"],
                    rank=row["rank"],
                    daily_credits=float(row["daily_credits"]),
                    max_active_workspaces=row["max_active_workspaces"],
                    max_concurrent_requests=row["max_concurrent_requests"],
                    is_default=row["is_default"],
                )
                by_id[plan.id] = plan
                by_name[plan.name] = plan
                if plan.is_default:
                    default = plan

            self._plans_by_id = by_id
            self._plans_by_name = by_name
            self._default_plan = default or (list(by_id.values())[0] if by_id else _FALLBACK_PLAN)
            self._loaded_at = time.monotonic()
            logger.info(f"[PlanService] Loaded {len(by_id)} plans")

        except Exception as e:
            logger.warning(f"[PlanService] DB load failed, using fallback: {e}")
            if not self._plans_by_id:
                self._plans_by_id = {_FALLBACK_PLAN.id: _FALLBACK_PLAN}
                self._plans_by_name = {_FALLBACK_PLAN.name: _FALLBACK_PLAN}
                self._default_plan = _FALLBACK_PLAN
                self._loaded_at = time.monotonic()

    async def ensure_loaded(self) -> None:
        """Refresh if not yet loaded or TTL expired."""
        config = get_usage_limits_config()
        ttl = config.get("plan_cache_ttl", 300)
        if not self._plans_by_id or (time.monotonic() - self._loaded_at) > ttl:
            await self.refresh()

    # ── sync lookups (pure dict reads) ───────────────────────────
    def get_plan(self, plan_id: Optional[int]) -> PlanInfo:
        if plan_id is not None and plan_id in self._plans_by_id:
            return self._plans_by_id[plan_id]
        return self.get_default_plan()

    def get_plan_by_name(self, name: str) -> Optional[PlanInfo]:
        return self._plans_by_name.get(name)

    def get_default_plan(self) -> PlanInfo:
        return self._default_plan or _FALLBACK_PLAN

    def get_all_plans(self) -> List[PlanInfo]:
        return sorted(self._plans_by_id.values(), key=lambda p: p.rank)

    def get_rank(self, plan_id: int) -> int:
        plan = self._plans_by_id.get(plan_id)
        return plan.rank if plan else -1
