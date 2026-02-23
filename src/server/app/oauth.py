"""
OAuth Router — Connect external OAuth providers (e.g. ChatGPT Codex).

Device Code Flow (RFC 8628):
1. POST /device/initiate — Backend requests device code from OpenAI → return {user_code, verification_url}
2. Frontend shows: "Visit [url] and enter code: XXXX-XXXX"
3. Frontend polls POST /device/poll every 5s
4. When user approves in browser, poll returns {success: true} and tokens are stored

Endpoints:
- POST   /api/v1/oauth/codex/device/initiate — Start device code flow
- POST   /api/v1/oauth/codex/device/poll     — Poll for user approval
- GET    /api/v1/oauth/codex/status           — Check connection status
- DELETE /api/v1/oauth/codex                  — Disconnect (delete tokens)
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from src.server.utils.api import CurrentUserId
from src.server.services.codex_oauth import (
    CODEX_PROVIDER,
    CODEX_DEVICE_VERIFY_URL,
    exchange_device_code,
    parse_jwt_claims,
    poll_device_authorization,
    request_device_code,
)
from src.server.database.oauth_tokens import (
    delete_oauth_tokens,
    get_oauth_status,
    upsert_oauth_tokens,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/oauth", tags=["OAuth"])


# ─── Device Code: Initiate ────────────────────────────────────────────────────

@router.post("/codex/device/initiate")
async def codex_device_initiate(user_id: CurrentUserId):
    """Start device code flow. Returns user_code + verification URL.

    The frontend should:
    1. Display the user_code prominently
    2. Open verification_url in a new tab
    3. Start polling /device/poll every `interval` seconds
    """
    from src.utils.cache.redis_cache import get_cache_client

    cache = get_cache_client()
    if not cache.enabled or not cache.client:
        raise HTTPException(status_code=503, detail="Cache unavailable for OAuth")

    try:
        device = await request_device_code()
    except Exception as e:
        logger.error(f"[oauth] Device code request failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to request device code from OpenAI")

    # Store device_auth_id + user_code in Redis (15-min TTL matching OpenAI's expiry)
    await cache.client.set(
        f"oauth:device:{user_id}",
        json.dumps({
            "device_auth_id": device["device_auth_id"],
            "user_code": device["user_code"],
        }),
        ex=900,
    )

    logger.info(f"[oauth] Device code initiated for user_id={user_id}")
    return {
        "user_code": device["user_code"],
        "verification_url": CODEX_DEVICE_VERIFY_URL,
        "interval": device["interval"],
    }


# ─── Device Code: Poll ────────────────────────────────────────────────────────

@router.post("/codex/device/poll")
async def codex_device_poll(user_id: CurrentUserId):
    """Poll for device authorization.

    Returns:
        {pending: true} if user hasn't approved yet
        {success: true, email, plan_type, account_id} on approval
    """
    from src.utils.cache.redis_cache import get_cache_client

    cache = get_cache_client()
    if not cache.enabled or not cache.client:
        raise HTTPException(status_code=503, detail="Cache unavailable")

    raw = await cache.client.get(f"oauth:device:{user_id}")
    if not raw:
        raise HTTPException(status_code=400, detail="No pending device authorization. Please initiate again.")

    device = json.loads(raw)

    try:
        result = await poll_device_authorization(device["device_auth_id"], device["user_code"])
    except Exception as e:
        logger.error(f"[oauth] Device poll error for user_id={user_id}: {e}")
        raise HTTPException(status_code=502, detail="Failed to poll OpenAI")

    if result is None:
        return {"pending": True}

    # User approved — exchange authorization code for tokens
    try:
        tokens = await exchange_device_code(result["authorization_code"], result["code_verifier"])

        # Parse JWT claims
        claims = parse_jwt_claims(tokens.get("id_token", ""))
        if not claims.get("account_id"):
            at_claims = parse_jwt_claims(tokens.get("access_token", ""))
            if at_claims.get("account_id"):
                claims["account_id"] = at_claims["account_id"]

        exp_ts = claims.get("exp")
        expires_at = (
            datetime.fromtimestamp(exp_ts, tz=timezone.utc)
            if exp_ts
            else datetime.now(timezone.utc) + timedelta(hours=1)
        )

        await upsert_oauth_tokens(
            user_id=user_id,
            provider=CODEX_PROVIDER,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            account_id=claims.get("account_id", ""),
            email=claims.get("email"),
            plan_type=claims.get("plan_type"),
            expires_at=expires_at,
        )

        # Clean up Redis
        await cache.client.delete(f"oauth:device:{user_id}")

        logger.info(
            f"[oauth] Codex connected for user_id={user_id} "
            f"email={claims.get('email')} plan={claims.get('plan_type')}"
        )
        return {
            "success": True,
            "email": claims.get("email"),
            "plan_type": claims.get("plan_type"),
            "account_id": claims.get("account_id", ""),
        }

    except Exception as e:
        logger.error(f"[oauth] Device code exchange failed for user_id={user_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {e}")


# ─── Status ──────────────────────────────────────────────────────────────────

@router.get("/codex/status")
async def codex_status(user_id: CurrentUserId):
    """Return connection status (no token decryption — fast check)."""
    status = await get_oauth_status(user_id, CODEX_PROVIDER)
    return status


# ─── Disconnect ──────────────────────────────────────────────────────────────

@router.delete("/codex")
async def codex_disconnect(user_id: CurrentUserId):
    """Delete stored OAuth tokens."""
    await delete_oauth_tokens(user_id, CODEX_PROVIDER)
    logger.info(f"[oauth] Codex disconnected for user_id={user_id}")
    return {"success": True}
