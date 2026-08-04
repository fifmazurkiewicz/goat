"""Lokalny login email/hasło — wyłącznie `ENVIRONMENT=local`.

Produkcja (Render) używa Supabase OAuth + JWKS. Ten moduł nie jest ładowany
w ścieżce produkcyjnej poza guardem w routerze auth.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import settings
from app.repositories.profiles_repo import ProfilesRepo

_LOCAL_JWT_ALGORITHM = "HS256"
_LOCAL_JWT_TTL = timedelta(days=7)
_ADMIN_EMAIL = "fmazurkiewicz@gmail.com"


def create_local_access_token(user_id: str, email: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "email": email,
        "role": "authenticated",
        "iat": now,
        "exp": now + _LOCAL_JWT_TTL,
    }
    secret = settings.local_jwt_secret.get_secret_value()
    return jwt.encode(payload, secret, algorithm=_LOCAL_JWT_ALGORITHM)


def decode_local_access_token(token: str) -> dict[str, Any]:
    secret = settings.local_jwt_secret.get_secret_value()
    return jwt.decode(
        token,
        secret,
        algorithms=[_LOCAL_JWT_ALGORITHM],
        options={"verify_aud": False},
    )


def verify_dev_credentials(email: str, password: str) -> bool:
    expected_email = (settings.dev_auth_email or "").strip().lower()
    expected_password = settings.dev_auth_password
    if not expected_email or expected_password is None:
        return False
    return email.strip().lower() == expected_email and password == expected_password.get_secret_value()


async def bootstrap_dev_user(conn: AsyncConnection, user_id: str, email: str) -> None:
    """Upewnia się, że lokalny stub `auth.users` i `profiles` istnieją."""
    await conn.execute(
        text(
            """
            INSERT INTO auth.users (id, email)
            VALUES (:user_id, :email)
            ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
            """
        ),
        {"user_id": user_id, "email": email},
    )

    repo = ProfilesRepo(conn)
    profile = await repo.get(user_id)
    if profile is None:
        await repo.ensure(user_id)

    if email.strip().lower() == _ADMIN_EMAIL:
        await conn.execute(
            text("UPDATE profiles SET is_admin = true WHERE id = :user_id"),
            {"user_id": user_id},
        )
