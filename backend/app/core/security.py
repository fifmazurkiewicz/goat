"""Supabase JWT verification (JWKS) + auth context for dependency injection.

Pattern from docs/technical/architecture.md section 2/8 and docs/technical/devops.md
section 5: `PyJWKClient(cache_keys=True, lifespan=300)` — caches keys, doesn't fetch
JWKS on every request. `sub` claim = user_id, the same contract RLS policies expect
(`auth.uid()` reads `request.jwt.claims->>'sub'`, see database-schema.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import jwt
import structlog
from fastapi import Depends, Header
from jwt import PyJWKClient

from app.core.config import settings
from app.core.db import service_role_connection
from app.core.dev_auth import decode_local_access_token
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.repositories.profiles_repo import ProfilesRepo

logger = structlog.get_logger(__name__)

_ALGORITHMS = ["RS256", "ES256"]


@lru_cache
def get_jwks_client() -> PyJWKClient:
    """Lazy-initialized, cached JWKS client (one per process, `lru_cache` instead of
    module-load initialization — avoids network I/O on module import / in tests)."""
    if not settings.supabase_jwks_url:
        raise RuntimeError("SUPABASE_JWKS_URL is not configured.")
    return PyJWKClient(settings.supabase_jwks_url, cache_keys=True, lifespan=300)


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Authenticated user context derived from the verified Supabase JWT."""

    user_id: str
    claims: dict[str, Any] = field(default_factory=dict)


def _extract_bearer_token(authorization: str) -> str:
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise UnauthorizedError("Oczekiwano nagłówka 'Authorization: Bearer <token>'.")
    return parts[1].strip()


def _verify_supabase_token(token: str) -> AuthContext:
    try:
        signing_key = get_jwks_client().get_signing_key_from_jwt(token)
        claims: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=_ALGORITHMS,
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        logger.warning("jwt_verification_failed", error=str(exc))
        raise UnauthorizedError("Nieprawidłowy lub wygasły token.") from exc

    user_id = claims.get("sub")
    if not user_id:
        raise UnauthorizedError("Token nie zawiera wymaganego claimu 'sub'.")

    return AuthContext(user_id=str(user_id), claims=claims)


def _verify_local_token(token: str) -> AuthContext:
    try:
        claims = decode_local_access_token(token)
    except jwt.PyJWTError as exc:
        logger.warning("local_jwt_verification_failed", error=str(exc))
        raise UnauthorizedError("Nieprawidłowy lub wygasły token.") from exc

    user_id = claims.get("sub")
    if not user_id:
        raise UnauthorizedError("Token nie zawiera wymaganego claimu 'sub'.")

    return AuthContext(user_id=str(user_id), claims=claims)


async def get_current_user(authorization: str = Header(...)) -> AuthContext:
    """FastAPI dependency: parses `Authorization: Bearer <token>`, verifies the JWT
    (local HS256 with `ENVIRONMENT=local`, Supabase JWKS in production)."""
    token = _extract_bearer_token(authorization)

    if settings.dev_auth_enabled:
        return _verify_local_token(token)
    return _verify_supabase_token(token)


async def require_admin(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
    """Dependency for `/admin/*` — explicit, code-level verification of `profiles.is_admin`
    (docs/technical/security.md section 2: "hiding in UI is not authorization"),
    executed in `service_role` context (architecture.md section 2, ADR-3) — RLS on
    `profiles` would give a regular user visibility only to their own row, while the
    admin must be able to verify this independently of whether their own profile is
    even readable by RLS in a given context.

    Raises `ForbiddenError` (403) when the profile doesn't exist or `is_admin=False`.
    """
    async with service_role_connection() as conn:
        profile = await ProfilesRepo(conn).get(auth.user_id)

    if profile is None or not profile.is_admin:
        raise ForbiddenError("Administrator permissions required.")

    return auth
