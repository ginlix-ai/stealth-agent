"""
FastAPI dependencies for usage limit enforcement.

Provides two dependencies that compose with get_current_user_id:
- ChatRateLimited: Enforces daily credit limit + burst guard
- WorkspaceLimitCheck: Enforces active workspace limits

Open-source mode (AUTH_SERVICE_URL unset): all operations allowed, no limits.
Commercial mode (AUTH_SERVICE_URL set): calls ginlix-auth for quota checks.
"""

import logging
import os
from dataclasses import dataclass
from typing import Annotated, Optional

import httpx
from fastapi import Depends, HTTPException

from src.config.settings import AUTH_ENABLED, AUTH_SERVICE_URL
from src.server.utils.api import get_current_user_id

logger = logging.getLogger(__name__)

# Default burst limit when ginlix-auth doesn't specify one
_DEFAULT_MAX_CONCURRENT = 10
_BURST_COUNTER_TTL = 300  # seconds

# Shared httpx client (created lazily)
_http_client: Optional[httpx.AsyncClient] = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=5.0)
    return _http_client


@dataclass
class ChatAuthResult:
    """Result from chat rate-limit dependency, carrying BYOK status to avoid re-querying."""
    user_id: str
    byok_active: bool = False


async def _get_bearer_token() -> Optional[str]:
    """Extract the raw bearer token from the current request context.

    This is a simplified helper — in practice the token is available from
    the FastAPI request.  We piggy-back on the jwt_bearer module's scheme.
    """
    # We can't easily get the raw token here without adding a dependency.
    # Instead, the enforce_chat_limit dependency receives the token via a
    # nested dependency.  See _call_validate_with_token below.
    return None


async def _call_validate(
    token: str,
    check_quota: Optional[str] = None,
    byok: bool = False,
) -> Optional[dict]:
    """Call ginlix-auth POST /api/auth/validate with optional quota check.

    Returns the parsed JSON response, or None on failure (fail-open).
    """
    if not AUTH_SERVICE_URL:
        return None

    client = _get_http_client()
    headers = {"Authorization": f"Bearer {token}"}
    body = {}
    if check_quota:
        body["check_quota"] = check_quota
    if byok:
        body["byok"] = True

    try:
        resp = await client.post(
            f"{AUTH_SERVICE_URL.rstrip('/')}/api/auth/validate",
            json=body if body else None,
            headers=headers,
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning(
            "ginlix-auth validate returned %d: %s", resp.status_code, resp.text[:200]
        )
        return None
    except Exception as e:
        logger.warning("ginlix-auth unreachable, failing open: %s", e)
        return None


# ---------------------------------------------------------------------------
# Burst guard (local Redis INCR/DECR — stays in langalpha)
# ---------------------------------------------------------------------------

async def _check_burst_guard(user_id: str, max_concurrent: int) -> dict:
    """Redis-based burst guard: INCR on entry, DECR on release."""
    from src.utils.cache.redis_cache import get_cache_client

    cache = get_cache_client()
    if not cache.enabled or not cache.client:
        return {"allowed": True}

    key = f"usage:burst:{user_id}"
    try:
        pipe = cache.client.pipeline()
        pipe.incr(key)
        pipe.expire(key, _BURST_COUNTER_TTL)
        results = await pipe.execute()
        current = results[0]

        if current > max_concurrent:
            # Roll back
            await cache.client.decr(key)
            return {"allowed": False, "current": current - 1, "limit": max_concurrent}

        return {"allowed": True, "current": current, "limit": max_concurrent}
    except Exception as e:
        logger.warning("Burst guard Redis error, allowing request: %s", e)
        return {"allowed": True}


async def release_burst_slot(user_id: str) -> None:
    """Release a burst slot (DECR) after request completes."""
    if not AUTH_SERVICE_URL:
        return  # No burst guard in open-source mode

    from src.utils.cache.redis_cache import get_cache_client

    cache = get_cache_client()
    if not cache.enabled or not cache.client:
        return

    key = f"usage:burst:{user_id}"
    try:
        current = await cache.client.decr(key)
        if current < 0:
            await cache.client.set(key, 0, ex=_BURST_COUNTER_TTL)
    except Exception as e:
        logger.warning("Burst guard release error: %s", e)


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

async def enforce_chat_limit(
    user_id: str = Depends(get_current_user_id),
) -> ChatAuthResult:
    """
    FastAPI dependency: enforce daily credit limit + burst guard.

    Open-source mode (no AUTH_SERVICE_URL): always allowed.
    Commercial mode: calls ginlix-auth for credit check, local Redis burst guard.
    BYOK users bypass credit check but still face burst guard.

    Returns ChatAuthResult on success, raises HTTPException(429) if over limit.
    """
    # Open-source mode or auth disabled: no limits
    if not AUTH_SERVICE_URL or not AUTH_ENABLED:
        return ChatAuthResult(user_id=user_id)

    # Check BYOK status locally (it's an LLM key concern, stays in langalpha)
    from src.server.database.api_keys import is_byok_active

    byok = await is_byok_active(user_id)

    if byok:
        # BYOK: no credit check, but still enforce burst guard
        # Get max_concurrent from ginlix-auth (cached via scopes call) or use default
        max_concurrent = _DEFAULT_MAX_CONCURRENT
        burst_result = await _check_burst_guard(user_id, max_concurrent)
        if not burst_result["allowed"]:
            raise HTTPException(
                status_code=429,
                detail={
                    "message": "Too many concurrent requests",
                    "type": "burst_limit",
                    "retry_after": 5,
                },
                headers={"Retry-After": "5"},
            )
        return ChatAuthResult(user_id=user_id, byok_active=True)

    # Non-BYOK: call ginlix-auth for full credit check
    result = await _call_validate_for_user(user_id, check_quota="chat")

    if result is None:
        # Fail-open: ginlix-auth unreachable
        return ChatAuthResult(user_id=user_id)

    quota = result.get("quota")
    if not quota:
        return ChatAuthResult(user_id=user_id)

    # Burst guard (local, using max_concurrent from response)
    max_concurrent = quota.get("max_concurrent_requests") or _DEFAULT_MAX_CONCURRENT
    burst_result = await _check_burst_guard(user_id, max_concurrent)
    if not burst_result["allowed"]:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Too many concurrent requests",
                "type": "burst_limit",
                "retry_after": 5,
            },
            headers={"Retry-After": "5"},
        )

    if not quota.get("allowed", True):
        limit_type = quota.get("limit_type", "credit_limit")
        if limit_type == "credit_limit":
            message = "Daily credit limit reached"
        else:
            message = "Too many concurrent requests, please wait"

        raise HTTPException(
            status_code=429,
            detail={
                "message": message,
                "type": limit_type,
                "used_credits": quota.get("used_credits"),
                "credit_limit": quota.get("credit_limit"),
                "remaining_credits": quota.get("remaining_credits"),
                "retry_after": quota.get("retry_after", 30),
            },
            headers={
                "Retry-After": str(quota.get("retry_after") or 30),
                "X-RateLimit-Limit": str(quota.get("credit_limit", "")),
                "X-RateLimit-Remaining": str(quota.get("remaining_credits", "")),
            },
        )

    return ChatAuthResult(user_id=user_id)


async def _call_validate_for_user(
    user_id: str,
    check_quota: Optional[str] = None,
    byok: bool = False,
) -> Optional[dict]:
    """Call ginlix-auth validate using internal service token or user_id header."""
    if not AUTH_SERVICE_URL:
        return None

    client = _get_http_client()
    headers = {"X-User-Id": user_id}

    # Use internal service token if available
    internal_token = os.getenv("INTERNAL_SERVICE_TOKEN", "")
    if internal_token:
        headers["Authorization"] = f"Bearer {internal_token}"

    body = {}
    if check_quota:
        body["check_quota"] = check_quota
    if byok:
        body["byok"] = True

    try:
        resp = await client.post(
            f"{AUTH_SERVICE_URL.rstrip('/')}/api/auth/validate",
            json=body if body else None,
            headers=headers,
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning(
            "ginlix-auth validate returned %d: %s", resp.status_code, resp.text[:200]
        )
        return None
    except Exception as e:
        logger.warning("ginlix-auth unreachable, failing open: %s", e)
        return None


async def enforce_workspace_limit(
    user_id: str = Depends(get_current_user_id),
) -> str:
    """
    FastAPI dependency: enforce active workspace limit.

    Open-source mode: no limits.
    Commercial mode: calls ginlix-auth for workspace quota check.

    Returns user_id on success, raises HTTPException(429) if at limit.
    """
    if not AUTH_SERVICE_URL or not AUTH_ENABLED:
        return user_id

    result = await _call_validate_for_user(user_id, check_quota="workspace")

    if result is None:
        return user_id  # Fail-open

    quota = result.get("quota")
    if not quota:
        return user_id

    if not quota.get("allowed", True):
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Active workspace limit reached",
                "type": "workspace_limit",
                "current": quota.get("active_workspaces"),
                "limit": quota.get("workspace_limit"),
                "remaining": 0,
            },
            headers={
                "X-RateLimit-Limit": str(quota.get("workspace_limit", "")),
                "X-RateLimit-Remaining": "0",
            },
        )

    return user_id


# ---------------------------------------------------------------------------
# Scope-based feature gating (Phase 2)
# ---------------------------------------------------------------------------

# Cache for user scopes: {user_id: (scopes_list, expiry_timestamp)}
_scope_cache: dict[str, tuple[list[str], float]] = {}
_SCOPE_CACHE_TTL = 300  # 5 minutes


async def _get_user_scopes(user_id: str) -> list[str]:
    """Get user's scopes from ginlix-auth (cached)."""
    import time

    now = time.time()
    cached = _scope_cache.get(user_id)
    if cached and cached[1] > now:
        return cached[0]

    result = await _call_validate_for_user(user_id)
    if result and "scopes" in result:
        scopes = result["scopes"]
    else:
        scopes = []  # Fail-open: no scopes restriction

    _scope_cache[user_id] = (scopes, now + _SCOPE_CACHE_TTL)
    return scopes


def require_scope(scope: str):
    """FastAPI dependency factory — checks user has scope. No-op when AUTH_SERVICE_URL unset."""
    async def check(user_id: str = Depends(get_current_user_id)):
        if not AUTH_SERVICE_URL:
            return user_id  # Open-source: everything allowed
        scopes = await _get_user_scopes(user_id)
        if scopes and scope not in scopes:
            raise HTTPException(403, detail=f"Requires scope: {scope}")
        return user_id
    return Depends(check)


# Annotated types for cleaner endpoint signatures
ChatRateLimited = Annotated[ChatAuthResult, Depends(enforce_chat_limit)]
WorkspaceLimitCheck = Annotated[str, Depends(enforce_workspace_limit)]
