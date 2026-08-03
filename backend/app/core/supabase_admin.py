"""Klient Supabase Admin API (`/auth/v1/admin/*`, GoTrue REST) — WYŁĄCZNIE dla `/admin/*`.

Osobny transport od `service_role_connection` (Postgres) — to REST API Supabase Auth,
nie baza. Używany do (1) dociągnięcia `email` per user do `GET /admin/users` (`profiles`
nie duplikuje `auth.users.email` — jedyne źródło prawdy to Auth), (2) resetu hasła.
"""

from __future__ import annotations

import secrets
from functools import lru_cache

import httpx
import structlog

from app.core.config import settings
from app.core.exceptions import ExternalServiceError

logger = structlog.get_logger(__name__)


class SupabaseAdminClient:
    def __init__(self) -> None:
        key = settings.supabase_service_role_key.get_secret_value()
        self._client = httpx.AsyncClient(
            base_url=f"{settings.supabase_url}/auth/v1/admin",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=httpx.Timeout(15.0, connect=5.0),
        )

    async def list_user_emails(self) -> dict[str, str]:
        """`GET /auth/v1/admin/users` (paginowane) -> `{user_id: email}` dla wzbogacenia
        `GET /admin/users` (ADR-16 wymaga emaila, którego `profiles` nie ma).

        Fail-open: awaria zwraca pusty dict zamiast wyjątku — lista kont z `profiles`
        (limity, budżet) jest ważniejsza niż wzbogacenie o email, nie chcemy wywalać
        całego `/admin/users` przez przejściową awarię Auth API.
        """
        emails: dict[str, str] = {}
        page = 1
        try:
            while True:
                response = await self._client.get(
                    "/users", params={"page": page, "per_page": 1000}
                )
                if response.status_code >= 400:
                    logger.warning(
                        "supabase_admin_list_users_failed", status=response.status_code
                    )
                    break
                users = response.json().get("users", [])
                if not users:
                    break
                for user in users:
                    if user.get("id") and user.get("email"):
                        emails[user["id"]] = user["email"]
                if len(users) < 1000:
                    break
                page += 1
        except httpx.HTTPError as exc:
            logger.warning("supabase_admin_list_users_error", error=str(exc))
        return emails

    async def reset_password(self, user_id: str) -> str:
        """Ustawia NOWE, losowe hasło tymczasowe (`PUT /admin/users/{id}`) i zwraca je do
        jednorazowego wyświetlenia adminowi (przekazywane userowi poza aplikacją).

        ZAŁOŻENIE / WĄTPLIWOŚĆ: dokumentacja mówi tylko "reset hasła przez Supabase Admin
        API" bez dalszych szczegółów mechaniki. Ten wariant (losowe hasło tymczasowe)
        jest wybrany zamiast `generate_link(type=recovery)`, bo to drugie wymaga
        skonfigurowanego SMTP po stronie projektu Supabase (nie zawsze dostępne, zwłaszcza
        w dev) — losowe hasło działa deterministycznie niezależnie od konfiguracji maila.
        """
        temp_password = secrets.token_urlsafe(12)
        response = await self._client.put(
            f"/users/{user_id}", json={"password": temp_password}
        )
        if response.status_code >= 400:
            raise ExternalServiceError(
                f"Supabase Admin API zwróciło błąd {response.status_code} przy resecie hasła."
            )
        return temp_password

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_supabase_admin_client() -> SupabaseAdminClient:
    return SupabaseAdminClient()
