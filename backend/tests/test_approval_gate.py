"""User approval gate — 403 pending, GET /account ungated, admin PATCH, no self-revoke."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import ForbiddenError
from app.core.security import AuthContext, get_current_user, require_admin
from app.main import app
from app.repositories.profiles_repo import ProfileRow


def _profile(*, is_approved: bool, is_admin: bool = False, user_id: str = "u1") -> ProfileRow:
    return ProfileRow(
        id=user_id,
        is_admin=is_admin,
        is_approved=is_approved,
        max_active_personas=5,
        nick=None,
        usage_budget_usd=10.0,
        created_at=datetime.now(timezone.utc),
    )


def _auth(*, user_id: str = "u1", email: str = "user@example.com") -> AuthContext:
    return AuthContext(user_id=user_id, claims={"sub": user_id, "email": email})


@asynccontextmanager
async def _fake_conn(_claims: object = None):
    yield MagicMock()


@pytest.fixture
def client_factory():
    async def _client() -> AsyncClient:
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    return _client


@pytest.mark.asyncio
async def test_unapproved_user_gets_pending_approval_on_feature_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _profile(is_approved=False)

    class FakeRepo:
        def __init__(self, _conn: object) -> None:
            pass

        async def ensure(self, _user_id: str, email: str | None = None) -> ProfileRow:
            return profile

        async def get(self, _user_id: str) -> ProfileRow:
            return profile

    monkeypatch.setattr("app.core.security.service_role_connection", _fake_conn)
    monkeypatch.setattr("app.core.security.ProfilesRepo", FakeRepo)

    async def fake_auth() -> AuthContext:
        return _auth()

    app.dependency_overrides[get_current_user] = fake_auth
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/api/v1/personas")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert res.status_code == 403
    body = res.json()
    assert body["error"]["code"] == "account_pending_approval"


@pytest.mark.asyncio
async def test_unapproved_user_can_read_account(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = _profile(is_approved=False)

    class FakeRepo:
        def __init__(self, _conn: object) -> None:
            pass

        async def get(self, _user_id: str) -> ProfileRow:
            return profile

        async def ensure(self, _user_id: str, email: str | None = None) -> ProfileRow:
            return profile

    monkeypatch.setattr("app.api.routers.account.rls_connection", _fake_conn)
    monkeypatch.setattr("app.api.routers.account.service_role_connection", _fake_conn)
    monkeypatch.setattr("app.api.routers.account.ProfilesRepo", FakeRepo)

    async def fake_auth() -> AuthContext:
        return _auth()

    app.dependency_overrides[get_current_user] = fake_auth
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/api/v1/account")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert res.status_code == 200
    body = res.json()
    assert body["is_approved"] is False
    assert body["id"] == "u1"


@pytest.mark.asyncio
async def test_health_remains_ungated() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_admin_patch_approval_accepts_user(monkeypatch: pytest.MonkeyPatch) -> None:
    updated = _profile(is_approved=True, user_id="u2")
    calls: list[tuple[str, bool]] = []

    class FakeRepo:
        def __init__(self, _conn: object) -> None:
            pass

        async def update_is_approved(self, user_id: str, is_approved: bool) -> ProfileRow:
            calls.append((user_id, is_approved))
            return updated

        async def get(self, user_id: str) -> ProfileRow:
            return _profile(is_approved=True, is_admin=True, user_id=user_id)

        async def list_all(self) -> list[ProfileRow]:
            return [updated]

    class FakeAudit:
        def __init__(self, _conn: object) -> None:
            pass

        async def log(self, **_kwargs: object) -> None:
            return None

    class FakeUsage:
        def __init__(self, _conn: object) -> None:
            pass

        async def list_for_period(self, _period: object) -> dict:
            return {}

    monkeypatch.setattr("app.api.routers.admin.service_role_connection", _fake_conn)
    monkeypatch.setattr("app.api.routers.admin.ProfilesRepo", FakeRepo)
    monkeypatch.setattr("app.api.routers.admin.AdminAuditRepo", FakeAudit)
    monkeypatch.setattr("app.api.routers.admin.UsageLimitsRepo", FakeUsage)

    async def fake_admin() -> AuthContext:
        return _auth(user_id="admin-1", email="fmazurkiewicz@gmail.com")

    app.dependency_overrides[require_admin] = fake_admin
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.patch(
                "/api/v1/admin/users/u2/approval",
                json={"is_approved": True},
            )
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert res.status_code == 200
    assert calls == [("u2", True)]
    assert res.json()["is_approved"] is True
    assert res.json()["usage_budget_usd"] == 10.0


@pytest.mark.asyncio
async def test_admin_cannot_revoke_self(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeRepo:
        def __init__(self, _conn: object) -> None:
            pass

        async def update_is_approved(self, _user_id: str, _is_approved: bool) -> ProfileRow:
            raise AssertionError("must not revoke self")

    monkeypatch.setattr("app.api.routers.admin.service_role_connection", _fake_conn)
    monkeypatch.setattr("app.api.routers.admin.ProfilesRepo", FakeRepo)

    async def fake_admin() -> AuthContext:
        return _auth(user_id="admin-1", email="fmazurkiewicz@gmail.com")

    app.dependency_overrides[require_admin] = fake_admin
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.patch(
                "/api/v1/admin/users/admin-1/approval",
                json={"is_approved": False},
            )
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert res.status_code == 403
    assert res.json()["error"]["code"] in {"forbidden", "account_pending_approval"}


@pytest.mark.asyncio
async def test_require_admin_rejects_unapproved_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = _profile(is_approved=False, is_admin=True)

    class FakeRepo:
        def __init__(self, _conn: object) -> None:
            pass

        async def get(self, _user_id: str) -> ProfileRow:
            return profile

        async def ensure(self, _user_id: str, email: str | None = None) -> ProfileRow:
            return profile

    monkeypatch.setattr("app.core.security.service_role_connection", _fake_conn)
    monkeypatch.setattr("app.core.security.ProfilesRepo", FakeRepo)

    with pytest.raises(ForbiddenError) as exc_info:
        await require_admin(_auth(user_id="admin-1"))

    assert exc_info.value.code == "account_pending_approval"
