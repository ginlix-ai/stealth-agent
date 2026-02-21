"""
MembershipService — singleton that caches membership definitions from the `memberships` DB table.

Usage:
    svc = MembershipService.get_instance()
    await svc.ensure_loaded()       # async — call once (or periodically)
    membership = svc.get_membership(membership_id)    # sync dict lookup after that
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.config.settings import get_usage_limits_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MembershipInfo:
    membership_id: int
    name: str
    display_name: str
    rank: int
    daily_credits: float
    max_active_workspaces: int
    max_concurrent_requests: int
    is_default: bool


# Hardcoded fallback if DB is unreachable on first boot
_FALLBACK_MEMBERSHIP = MembershipInfo(
    membership_id=1,
    name="free",
    display_name="Free",
    rank=0,
    daily_credits=50.0,
    max_active_workspaces=3,
    max_concurrent_requests=10,
    is_default=True,
)


class MembershipService:
    _instance: Optional["MembershipService"] = None

    def __init__(self) -> None:
        self._memberships_by_id: Dict[int, MembershipInfo] = {}
        self._memberships_by_name: Dict[str, MembershipInfo] = {}
        self._default_membership: Optional[MembershipInfo] = None
        self._loaded_at: float = 0.0

    # ── singleton ────────────────────────────────────────────────
    @classmethod
    def get_instance(cls) -> "MembershipService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── async DB loading ─────────────────────────────────────────
    async def refresh(self) -> None:
        """Load all memberships from DB into memory."""
        try:
            from src.server.database.conversation import get_db_connection
            from psycopg.rows import dict_row

            async with get_db_connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        "SELECT membership_id, name, display_name, rank, daily_credits, "
                        "max_active_workspaces, max_concurrent_requests, is_default "
                        "FROM memberships ORDER BY rank"
                    )
                    rows = await cur.fetchall()

            by_id: Dict[int, MembershipInfo] = {}
            by_name: Dict[str, MembershipInfo] = {}
            default: Optional[MembershipInfo] = None

            for row in rows:
                membership = MembershipInfo(
                    membership_id=row["membership_id"],
                    name=row["name"],
                    display_name=row["display_name"],
                    rank=row["rank"],
                    daily_credits=float(row["daily_credits"]),
                    max_active_workspaces=row["max_active_workspaces"],
                    max_concurrent_requests=row["max_concurrent_requests"],
                    is_default=row["is_default"],
                )
                by_id[membership.membership_id] = membership
                by_name[membership.name] = membership
                if membership.is_default:
                    default = membership

            self._memberships_by_id = by_id
            self._memberships_by_name = by_name
            self._default_membership = default or (list(by_id.values())[0] if by_id else _FALLBACK_MEMBERSHIP)
            self._loaded_at = time.monotonic()
            logger.info(f"[MembershipService] Loaded {len(by_id)} memberships")

        except Exception as e:
            logger.warning(f"[MembershipService] DB load failed, using fallback: {e}")
            if not self._memberships_by_id:
                self._memberships_by_id = {_FALLBACK_MEMBERSHIP.membership_id: _FALLBACK_MEMBERSHIP}
                self._memberships_by_name = {_FALLBACK_MEMBERSHIP.name: _FALLBACK_MEMBERSHIP}
                self._default_membership = _FALLBACK_MEMBERSHIP
                self._loaded_at = time.monotonic()

    async def ensure_loaded(self) -> None:
        """Refresh if not yet loaded or TTL expired."""
        config = get_usage_limits_config()
        ttl = config.get("membership_cache_ttl", config.get("plan_cache_ttl", 300))
        if not self._memberships_by_id or (time.monotonic() - self._loaded_at) > ttl:
            await self.refresh()

    # ── sync lookups (pure dict reads) ───────────────────────────
    def get_membership(self, membership_id: Optional[int]) -> MembershipInfo:
        if membership_id is not None and membership_id in self._memberships_by_id:
            return self._memberships_by_id[membership_id]
        return self.get_default_membership()

    def get_membership_by_name(self, name: str) -> Optional[MembershipInfo]:
        return self._memberships_by_name.get(name)

    def get_default_membership(self) -> MembershipInfo:
        return self._default_membership or _FALLBACK_MEMBERSHIP

    def get_all_memberships(self) -> List[MembershipInfo]:
        return sorted(self._memberships_by_id.values(), key=lambda m: m.rank)

    def get_rank(self, membership_id: int) -> int:
        membership = self._memberships_by_id.get(membership_id)
        return membership.rank if membership else -1
