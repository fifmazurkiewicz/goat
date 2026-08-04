"""Weryfikacja JWT Supabase (JWKS) + kontekst autentykacji dla dependency injection.

Wzorzec z docs/technical/architecture.md sekcja 2/8 i docs/technical/devops.md sekcja 5:
`PyJWKClient(cache_keys=True, lifespan=300)` — cache kluczy, nie fetch JWKS przy każdym
requeście. Claim `sub` = user_id, ten sam kontrakt którego oczekują polityki RLS
(`auth.uid()` czyta `request.jwt.claims->>'sub'`, patrz database-schema.md).
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
    """Lazy-initialized, cache'owany klient JWKS (jeden na proces, `lru_cache` zamiast
    inicjalizacji na module-load — unika sieciowego I/O przy imporcie modułu/w testach)."""
    if not settings.supabase_jwks_url:
        raise RuntimeError("SUPABASE_JWKS_URL nie jest skonfigurowany.")
    return PyJWKClient(settings.supabase_jwks_url, cache_keys=True, lifespan=300)


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Kontekst zalogowanego użytkownika wyprowadzony ze zweryfikowanego JWT Supabase."""

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
    """Dependency FastAPI: parsuje `Authorization: Bearer <token>`, weryfikuje JWT
    (lokalny HS256 przy `ENVIRONMENT=local`, Supabase JWKS w produkcji)."""
    token = _extract_bearer_token(authorization)

    if settings.dev_auth_enabled:
        return _verify_local_token(token)
    return _verify_supabase_token(token)


async def require_admin(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
    """Dependency dla `/admin/*` — jawna, kodowa weryfikacja `profiles.is_admin`
    (docs/technical/security.md sekcja 2: "ukrycie w UI to nie jest autoryzacja"),
    wykonana w kontekście `service_role` (architecture.md sekcja 2, ADR-3) — RLS na
    `profiles` dałby zwykłemu userowi widoczność wyłącznie własnego wiersza, a admin
    musi móc to sprawdzić niezależnie od tego, czy własny profil jest w ogóle czytelny
    przez RLS w danym kontekście.

    Rzuca `ForbiddenError` (403) gdy profil nie istnieje albo `is_admin=False`.
    """
    async with service_role_connection() as conn:
        profile = await ProfilesRepo(conn).get(auth.user_id)

    if profile is None or not profile.is_admin:
        raise ForbiddenError("Wymagane uprawnienia administratora.")

    return auth
