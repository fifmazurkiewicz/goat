"""Liveness test for the `/api/health` endpoint — see docs/technical/devops.md (Render Health Check)."""

from __future__ import annotations

from httpx import AsyncClient


async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}