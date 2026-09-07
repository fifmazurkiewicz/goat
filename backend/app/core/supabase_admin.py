"""Supabase Admin API client (`/auth/v1/admin/*`, GoTrue REST) — ONLY for `/admin/*`.

Separate transport from `service_role_connection` (Postgres) — this is the Supabase
Auth REST API, not the database. Used for (1) fetching `email` per user for
`GET /admin/users` (`profiles` doesn't duplicate `auth.users.email` — Auth is the
single source of truth), (2) password reset.
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
        if not settings.supabase_url or settings.supabase_service_role_key is None:
            self._client = None
            return
        key = settings.supabase_service_role_key.get_secret_value()
        self._client = httpx.AsyncClient(
            base_url=f"{settings.supabase_url}/auth/v1/admin",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=httpx.Timeout(15.0, connect=5.0),
        )

    async def list_user_emails(self) -> dict[str, str]:
        """`GET /auth/v1/admin/users` (paginated) -> `{user_id: email}` to enrich
        `GET /admin/users` (ADR-16 requires email, which `profiles` doesn't have).

        Fail-open: outage returns an empty dict instead of an exception — the account
        list with `profiles` (limits, budget) is more important than the email
        enrichment; we don't want to crash the whole `/admin/users` on a transient
        Auth API outage.
        """
        emails: dict[str, str] = {}
        if self._client is None:
            return emails
        page = 1
        try:
            while True:
                response = await self._client.get("/users", params={"page": page, "per_page": 1000})
                if response.status_code >= 400:
                    logger.warning("supabase_admin_list_users_failed", status=response.status_code)
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
        """Sets a NEW, random temporary password (`PUT /admin/users/{id}`) and returns
        it for one-time display to the admin (passed to the user outside the app).

        ASSUMPTION / DOUBT: the docs only say "reset password via Supabase Admin API"
        without further details on the mechanics. This variant (random temporary
        password) is chosen over `generate_link(type=recovery)` because the latter
        requires SMTP configured on the Supabase project side (not always available,
        especially in dev) — the random password works deterministically regardless
        of email configuration.
        """
        temp_password = secrets.token_urlsafe(12)
        if self._client is None:
            raise ExternalServiceError("Supabase Admin API niedostępne w trybie lokalnym (brak SUPABASE_URL).")
        response = await self._client.put(f"/users/{user_id}", json={"password": temp_password})
        if response.status_code >= 400:
            raise ExternalServiceError(f"Supabase Admin API zwróciło błąd {response.status_code} przy resecie hasła.")
        return temp_password

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()


@lru_cache
def get_supabase_admin_client() -> SupabaseAdminClient:
    return SupabaseAdminClient()
