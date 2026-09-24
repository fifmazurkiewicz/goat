"""Admin diagnostics endpoints expose database rows through JSON-safe DTOs."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import AuthContext, require_admin
from app.main import app
from app.repositories.admin_audit_repo import AdminAuditRepo


class _Result:
    def __init__(self, row: object) -> None:
        self._row = row

    def all(self) -> list[object]:
        return [self._row]

    def __iter__(self):
        return iter([self._row])


class _Connection:
    async def execute(self, *_args: object, **_kwargs: object) -> _Result:
        return _Result(
            SimpleNamespace(
                _mapping={
                    "id": UUID("00000000-0000-0000-0000-000000000001"),
                    "admin_user_id": UUID("00000000-0000-0000-0000-000000000002"),
                    "action": "edit_approval",
                    "target_user_id": UUID("00000000-0000-0000-0000-000000000003"),
                    "details": None,
                    "created_at": datetime(2026, 9, 24, tzinfo=UTC),
                }
            )
        )


@pytest.mark.asyncio
async def test_audit_repo_normalizes_uuid_columns() -> None:
    entry = (await AdminAuditRepo(_Connection()).list_all())[0]
    assert entry.id == "00000000-0000-0000-0000-000000000001"
    assert entry.target_user_id == "00000000-0000-0000-0000-000000000003"


@pytest.mark.asyncio
async def test_moderation_events_endpoint_is_available(monkeypatch: pytest.MonkeyPatch) -> None:
    @asynccontextmanager
    async def fake_connection():
        yield MagicMock()

    class FakeModerationRepo:
        def __init__(self, _conn: object) -> None:
            pass

        async def list_all(self):
            return [
                SimpleNamespace(
                    id="event-1",
                    user_id="user-1",
                    persona_id=None,
                    session_id=None,
                    message_id=None,
                    trigger_type="chat_heuristic",
                    raw_snippet=None,
                    classifier_verdict="clean",
                    reviewed=False,
                    created_at=datetime(2026, 9, 24, tzinfo=UTC),
                )
            ]

    monkeypatch.setattr("app.api.routers.admin.service_role_connection", fake_connection)
    monkeypatch.setattr("app.api.routers.admin.ModerationEventsRepo", FakeModerationRepo)

    async def fake_admin() -> AuthContext:
        return AuthContext(user_id="admin-1")

    app.dependency_overrides[require_admin] = fake_admin
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/admin/moderation-events")
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert response.status_code == 200
    assert response.json()[0]["id"] == "event-1"
