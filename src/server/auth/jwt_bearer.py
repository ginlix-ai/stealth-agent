"""
Supabase JWT verification.

Decodes asymmetric JWTs (RS256/ES256) using JWKS public keys fetched from the
Supabase project endpoint. Returns the user UUID from the `sub` claim and
optionally the ``auth_provider`` from ``app_metadata.provider``.

When ``SUPABASE_URL`` is **not set**, authentication is bypassed and all
requests are attributed to a default local-dev identity.  This lets
contributors run the stack locally without a Supabase project.
"""

from dataclasses import dataclass

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config.settings import AUTH_ENABLED, LOCAL_DEV_USER_ID, SUPABASE_URL

_bearer_scheme = HTTPBearer(auto_error=False)

_jwks_client: PyJWKClient | None = None


@dataclass(frozen=True)
class AuthInfo:
    """Decoded JWT fields needed by the auth-sync flow."""
    user_id: str
    auth_provider: str | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not SUPABASE_URL:
            raise RuntimeError("SUPABASE_URL environment variable is not set")
        jwks_url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=300)
    return _jwks_client


def _decode_token(token: str) -> AuthInfo:
    """Decode a Supabase JWT and return user UUID + auth provider."""
    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256", "ES256"],
            audience="authenticated",
        )
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token missing sub claim")
        auth_provider = payload.get("app_metadata", {}).get("provider")
        return AuthInfo(user_id=user_id, auth_provider=auth_provider)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def verify_jwt_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """FastAPI dependency — extracts Bearer token via HTTPBearer and verifies it.

    Returns the Supabase user UUID (``sub`` claim) which is used directly
    as ``user_id`` across all database tables.

    When Supabase auth is disabled (``SUPABASE_URL`` unset), returns a
    static local-dev user ID without requiring a token.
    """
    if not AUTH_ENABLED:
        return LOCAL_DEV_USER_ID
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return _decode_token(credentials.credentials).user_id


async def get_current_auth_info(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthInfo:
    """FastAPI dependency — returns both ``user_id`` and ``auth_provider``.

    Used by the auth-sync endpoint to persist the provider on first login.
    """
    if not AUTH_ENABLED:
        return AuthInfo(user_id=LOCAL_DEV_USER_ID)
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return _decode_token(credentials.credentials)
