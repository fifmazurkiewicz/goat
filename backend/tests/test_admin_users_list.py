"""Contract for `GET /api/v1/admin/users` — email must come from `auth.users`.

The Users column in `/admin` renders `email`. Enrichment used to call only the
Supabase Auth Admin REST API and fail-open to `{}` (local Postgres, Auth outage),
so the cell was empty even though `auth.users.email` exists.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import AuthContext, require_admin
from app.main import app
from app.repositories.profiles_repo import ProfileRow


def _profile(*, user_id: str = "u2", is_admin: bool = False) -> ProfileRow:
    return ProfileRow(
        id=user_id,
        is_admin=is_admin,
        is_approved=True,
        max_active_personas=5,
        nick=None,
        usage_budget_usd=10.0,
        created_at=datetime.now(UTC),
    )


@asynccontextmanager
async def _fake_conn(_claims: object = None):
    yield MagicMock()


@pytest.mark.asyncio
async def test_list_users_includes_email_from_auth_users_when_admin_api_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _profile()

    class FakeRepo:
        def __init__(self, _conn: object) -> None:
            pass

        async def list_all(self) -> list[ProfileRow]:
            return [profile]

        async def list_emails(self) -> dict[str, str]:
            return {profile.id: "other@example.com"}

    class FakeUsage:
        def __init__(self, _conn: object) -> None:
            pass

        async def list_for_period(self, _period: object) -> dict:
            return {}

    class FakeAdminClient:
        async def list_user_emails(self) -> dict[str, str]:
            return {}

    monkeypatch.setattr("app.api.routers.admin.service_role_connection", _fake_conn)
    monkeypatch.setattr("app.api.routers.admin.login_role_connection", _fake_conn)
    monkeypatch.setattr("app.api.routers.admin.ProfilesRepo", FakeRepo)
    monkeypatch.setattr("app.api.routers.admin.UsageLimitsRepo", FakeUsage)
    monkeypatch.setattr(
        "app.api.routers.admin.get_supabase_admin_client",
        lambda: FakeAdminClient(),
    )

    async def fake_admin() -> AuthContext:
        return AuthContext(
            user_id="admin-1",
            claims={"sub": "admin-1", "email": "fmazurkiewicz@gmail.com"},
        )

    app.dependency_overrides[require_admin] = fake_admin
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/api/v1/admin/users")
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["id"] == "u2"
    assert body[0]["email"] == "other@example.com"


@pytest.mark.asyncio
async def test_list_users_reads_emails_as_login_role_not_service_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hosted `auth.users` is not granted to `service_role`. Emails must be read
    on the DATABASE_URL login role (typically postgres), or the Users column is "—"."""
    profile = _profile()
    email_conn: dict[str, object] = {}

    @asynccontextmanager
    async def fake_service(_claims: object = None):
        yield "service-conn"

    @asynccontextmanager
    async def fake_login():
        yield "login-conn"

    class FakeRepo:
        def __init__(self, conn: object) -> None:
            self.conn = conn

        async def list_all(self) -> list[ProfileRow]:
            assert self.conn == "service-conn"
            return [profile]

        async def list_emails(self) -> dict[str, str]:
            email_conn["value"] = self.conn
            return {profile.id: "other@example.com"}

    class FakeUsage:
        def __init__(self, _conn: object) -> None:
            pass

        async def list_for_period(self, _period: object) -> dict:
            return {}

    class FakeAdminClient:
        async def list_user_emails(self) -> dict[str, str]:
            return {}

    monkeypatch.setattr("app.api.routers.admin.service_role_connection", fake_service)
    monkeypatch.setattr("app.api.routers.admin.login_role_connection", fake_login, raising=False)
    monkeypatch.setattr("app.api.routers.admin.ProfilesRepo", FakeRepo)
    monkeypatch.setattr("app.api.routers.admin.UsageLimitsRepo", FakeUsage)
    monkeypatch.setattr(
        "app.api.routers.admin.get_supabase_admin_client",
        lambda: FakeAdminClient(),
    )

    async def fake_admin() -> AuthContext:
        return AuthContext(
            user_id="admin-1",
            claims={"sub": "admin-1", "email": "fmazurkiewicz@gmail.com"},
        )

    app.dependency_overrides[require_admin] = fake_admin
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/api/v1/admin/users")
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert res.status_code == 200
    assert res.json()[0]["email"] == "other@example.com"
    assert email_conn["value"] == "login-conn"
