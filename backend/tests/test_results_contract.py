"""Contract: `GET /api/v1/results` exposes `details` (ADR-25) — same lesson as the
`tool_calls` hotfix: a DTO field the FE depends on must be pinned by a test."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.repositories.results_repo import ResultRow


@pytest.fixture
def _patched(monkeypatch: pytest.MonkeyPatch):
    @asynccontextmanager
    async def fake_rls(_claims: object):
        yield MagicMock()

    class FakeResultsRepo:
        def __init__(self, _conn: object) -> None:
            pass

        async def list_for_user(self, **_kwargs: object) -> list[ResultRow]:
            return [
                ResultRow(
                    id="r1",
                    user_id="u1",
                    category="strength",
                    metric="Dead bug",
                    value=50.0,
                    unit="kg",
                    logged_date=date(2026, 10, 11),
                    source="agent",
                    source_persona_id="p1",
                    is_custom=True,
                    notes=None,
                    created_at=datetime(2026, 10, 11, tzinfo=UTC),
                    details=[{"label": "Serie", "value": "3"}],
                )
            ]

    monkeypatch.setattr("app.api.routers.results.rls_connection", fake_rls)
    monkeypatch.setattr("app.api.routers.results.ResultsRepo", FakeResultsRepo)

    async def fake_auth() -> object:
        ctx = MagicMock()
        ctx.claims = {"sub": "u1"}
        ctx.user_id = "u1"
        return ctx

    from app.core.security import get_current_user, require_approved, require_health_consent

    for dep in (get_current_user, require_approved, require_health_consent):
        app.dependency_overrides[dep] = fake_auth
    yield
    for dep in (get_current_user, require_approved, require_health_consent):
        app.dependency_overrides.pop(dep, None)


@pytest.mark.asyncio
async def test_results_endpoint_returns_details(_patched) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/results?category=strength")
    assert res.status_code == 200
    assert res.json()[0]["details"] == [{"label": "Serie", "value": "3"}]
