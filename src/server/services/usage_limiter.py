"""
Usage limiter service for per-user, tier-based credit limiting.

Two enforcement layers:
1. **Credit limit** (DB): SUM(total_credits) from conversation_usage today.
   This is the real limit. Checked before each request.
2. **Burst guard** (Redis): INCR counter to cap concurrent in-flight requests.
   Prevents a user from firing many requests before any completes and writes credits.

Workspace limit uses a simple DB COUNT — unchanged.

Graceful degradation: if Redis or DB is down, requests are allowed (not blocked).
Complete no-op when auth is disabled.
"""

import logging
from datetime import datetime, timedelta, timezone

from src.server.auth.jwt_bearer import _AUTH_ENABLED
from src.config.settings import get_usage_limits_config
from src.server.services.membership_service import MembershipService, MembershipInfo

logger = logging.getLogger(__name__)


class UsageLimiter:
    """Static methods for usage limit checking."""

    @staticmethod
    def is_enabled() -> bool:
        """Check if usage limits are active (auth enabled + config enabled)."""
        if not _AUTH_ENABLED:
            return False
        config = get_usage_limits_config()
        return bool(config.get('enabled', False))

    # =====================================================================
    # Plan lookup (Redis-cached)
    # =====================================================================

    @staticmethod
    async def get_user_membership(user_id: str) -> MembershipInfo:
        """
        Get user's MembershipInfo with Redis caching (caches membership_id).

        Falls back to DB lookup on cache miss. Returns default membership on any error.
        """
        svc = MembershipService.get_instance()
        await svc.ensure_loaded()
        default = svc.get_default_membership()

        if not UsageLimiter.is_enabled():
            return default

        cache_key = f"user:membership:{user_id}"
        config = get_usage_limits_config()
        cache_ttl = config.get('membership_cache_ttl', config.get('plan_cache_ttl', 300))

        # Try Redis cache first (stores membership_id as int)
        try:
            from src.utils.cache.redis_cache import get_cache_client
            cache = get_cache_client()
            if cache.client:
                cached = await cache.client.get(cache_key)
                if cached:
                    membership_id = int(cached.decode() if isinstance(cached, bytes) else cached)
                    return svc.get_membership(membership_id)
        except Exception as e:
            logger.debug(f"[usage_limiter] Redis cache read failed: {e}")

        # Cache miss — query DB for membership_id
        try:
            from src.server.database.user import get_user
            user = await get_user(user_id)
            membership_id = user.get('membership_id') if user else None
        except Exception as e:
            logger.warning(f"[usage_limiter] DB lookup failed for {user_id}: {e}")
            return default

        membership = svc.get_membership(membership_id)

        # Write back to cache (store membership_id)
        try:
            from src.utils.cache.redis_cache import get_cache_client
            cache = get_cache_client()
            if cache.client:
                await cache.client.set(cache_key, str(membership.membership_id), ex=cache_ttl)
        except Exception as e:
            logger.debug(f"[usage_limiter] Redis cache write failed: {e}")

        return membership

    @staticmethod
    async def get_user_timezone(user_id: str) -> str:
        """Get user's timezone with Redis caching. Defaults to UTC."""
        cache_key = f"user:timezone:{user_id}"

        # Try Redis cache
        try:
            from src.utils.cache.redis_cache import get_cache_client
            cache = get_cache_client()
            if cache.client:
                cached = await cache.client.get(cache_key)
                if cached:
                    return cached.decode() if isinstance(cached, bytes) else cached
        except Exception:
            pass

        # Cache miss — query DB
        tz = "UTC"
        try:
            from src.server.database.user import get_user
            user = await get_user(user_id)
            tz = (user.get('timezone') or "UTC") if user else "UTC"
        except Exception as e:
            logger.debug(f"[usage_limiter] Failed to get timezone for {user_id}: {e}")

        # Write back to cache
        try:
            from src.utils.cache.redis_cache import get_cache_client
            cache = get_cache_client()
            if cache.client:
                await cache.client.set(cache_key, tz, ex=300)
        except Exception:
            pass

        return tz

    @staticmethod
    async def flush_plan_cache(user_id: str) -> None:
        """Delete the cached membership and burst counter for a user (call after plan upgrade)."""
        try:
            from src.utils.cache.redis_cache import get_cache_client
            cache = get_cache_client()
            if cache.client:
                await cache.client.delete(
                    f"user:membership:{user_id}",
                    f"usage:burst:{user_id}",
                )
        except Exception as e:
            logger.debug(f"[usage_limiter] Failed to flush plan cache: {e}")

    # =====================================================================
    # Credit-based chat limit
    # =====================================================================

    @staticmethod
    async def check_chat_limit(user_id: str) -> dict:
        """
        Check daily credit limit + burst guard.

        Two layers:
        1. DB credit check: SUM(total_credits) for today vs daily_credits tier limit
        2. Redis burst guard: INCR counter vs max_concurrent_requests

        Returns:
            {allowed, used_credits, credit_limit, remaining_credits, retry_after,
             burst_count, burst_limit}
        """
        if not UsageLimiter.is_enabled():
            return {
                'allowed': True, 'used_credits': 0.0, 'credit_limit': -1,
                'remaining_credits': -1, 'retry_after': None,
                'burst_count': 0, 'burst_limit': -1,
            }

        plan = await UsageLimiter.get_user_membership(user_id)
        daily_credit_limit = plan.daily_credits
        max_concurrent = plan.max_concurrent_requests

        # --- Layer 1: DB credit check ---
        if daily_credit_limit != -1:
            user_tz = await UsageLimiter.get_user_timezone(user_id)
            used_credits = await UsageLimiter.get_daily_credit_usage(user_id, user_tz)
            if used_credits >= daily_credit_limit:
                try:
                    from zoneinfo import ZoneInfo
                    now = datetime.now(ZoneInfo(user_tz))
                except Exception:
                    now = datetime.now(timezone.utc)
                next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                retry_after = int((next_midnight - now).total_seconds())
                return {
                    'allowed': False,
                    'used_credits': used_credits,
                    'credit_limit': daily_credit_limit,
                    'remaining_credits': 0.0,
                    'retry_after': retry_after,
                    'burst_count': 0,
                    'burst_limit': max_concurrent,
                }
        else:
            used_credits = 0.0  # Don't bother querying for unlimited

        # --- Layer 2: Redis burst guard ---
        if max_concurrent != -1:
            burst_result = await UsageLimiter._check_burst_guard(user_id, max_concurrent)
            if not burst_result['allowed']:
                return {
                    'allowed': False,
                    'used_credits': used_credits,
                    'credit_limit': daily_credit_limit,
                    'remaining_credits': max(0.0, daily_credit_limit - used_credits) if daily_credit_limit != -1 else -1,
                    'retry_after': 30,  # Short retry for burst
                    'burst_count': burst_result['count'],
                    'burst_limit': max_concurrent,
                }
            burst_count = burst_result['count']
        else:
            burst_count = 0

        remaining = max(0.0, daily_credit_limit - used_credits) if daily_credit_limit != -1 else -1

        return {
            'allowed': True,
            'used_credits': used_credits,
            'credit_limit': daily_credit_limit,
            'remaining_credits': remaining,
            'retry_after': None,
            'burst_count': burst_count,
            'burst_limit': max_concurrent,
        }

    @staticmethod
    async def release_burst_slot(user_id: str) -> None:
        """Decrement the burst counter after a request completes or is rejected."""
        try:
            from src.utils.cache.redis_cache import get_cache_client
            cache = get_cache_client()
            if cache.client:
                counter_key = f"usage:burst:{user_id}"
                val = await cache.client.decr(counter_key)
                # Don't let it go negative
                if val is not None and int(val) < 0:
                    await cache.client.set(counter_key, 0, keepttl=True)
        except Exception as e:
            logger.debug(f"[usage_limiter] Failed to release burst slot: {e}")

    @staticmethod
    async def _check_burst_guard(user_id: str, max_concurrent: int) -> dict:
        """
        Redis-based burst guard. Prevents too many concurrent in-flight requests.

        Returns:
            {allowed: bool, count: int}
        """
        config = get_usage_limits_config()
        burst_ttl = config.get('burst_counter_ttl', 300)
        counter_key = f"usage:burst:{user_id}"

        try:
            from src.utils.cache.redis_cache import get_cache_client
            cache = get_cache_client()
            if not cache.client:
                return {'allowed': True, 'count': 0}

            pipe = cache.client.pipeline()
            pipe.incr(counter_key)
            pipe.expire(counter_key, burst_ttl)
            results = await pipe.execute()
            current = results[0]

            if current > max_concurrent:
                # Over burst limit — roll back
                await cache.client.decr(counter_key)
                return {'allowed': False, 'count': current - 1}

            return {'allowed': True, 'count': current}

        except Exception as e:
            logger.warning(f"[usage_limiter] Redis burst guard failed: {e}")
            return {'allowed': True, 'count': 0}

    # =====================================================================
    # Credit usage from DB (source of truth)
    # =====================================================================

    @staticmethod
    async def get_daily_credit_usage(user_id: str, user_tz: str = "UTC") -> float:
        """
        Get today's total credits consumed from conversation_usages (DB truth).

        Uses the user's timezone to determine "today" so the daily window
        resets at midnight in their local time, not midnight UTC.
        """
        try:
            from src.server.database.conversation import get_db_connection
            from psycopg.rows import dict_row
            async with get_db_connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        """
                        SELECT COALESCE(SUM(total_credits), 0) as total
                        FROM conversation_usages
                        WHERE user_id = %s
                          AND created_at >= (CURRENT_DATE AT TIME ZONE %s)
                        """,
                        (user_id, user_tz),
                    )
                    result = await cur.fetchone()
                    return float(result['total']) if result else 0.0
        except Exception as e:
            logger.warning(f"[usage_limiter] DB credit query failed for {user_id}: {e}")
            return 0.0

    # =====================================================================
    # Workspace limit (count-based, unchanged)
    # =====================================================================

    @staticmethod
    async def check_workspace_limit(user_id: str) -> dict:
        """
        Check if user can create another workspace.

        Returns:
            {allowed: bool, current: int, limit: int, remaining: int}
        """
        if not UsageLimiter.is_enabled():
            return {'allowed': True, 'current': 0, 'limit': -1, 'remaining': -1}

        plan = await UsageLimiter.get_user_membership(user_id)
        max_workspaces = plan.max_active_workspaces

        if max_workspaces == -1:
            return {'allowed': True, 'current': 0, 'limit': -1, 'remaining': -1}

        active_count = await UsageLimiter.get_active_workspace_count(user_id)

        if active_count >= max_workspaces:
            return {
                'allowed': False,
                'current': active_count,
                'limit': max_workspaces,
                'remaining': 0,
            }

        return {
            'allowed': True,
            'current': active_count,
            'limit': max_workspaces,
            'remaining': max(0, max_workspaces - active_count),
        }

    @staticmethod
    async def get_active_workspace_count(user_id: str) -> int:
        """Count active workspaces for a user (creating or running status)."""
        try:
            from src.server.database.conversation import get_db_connection
            from psycopg.rows import dict_row
            async with get_db_connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        "SELECT COUNT(*) as cnt FROM workspaces WHERE user_id = %s AND status IN ('creating', 'running')",
                        (user_id,),
                    )
                    result = await cur.fetchone()
                    return result['cnt'] if result else 0
        except Exception as e:
            logger.warning(f"[usage_limiter] Failed to count workspaces for {user_id}: {e}")
            return 0
