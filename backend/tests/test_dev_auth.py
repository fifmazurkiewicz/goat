"""Testy lokalnego loginu email/hasło."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_dev_login_wrong_password(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/dev-login",
        json={"email": "dev@example.com", "password": "wrong"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dev_login_disabled_in_production(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routers.auth.settings", "environment", "production")
    response = await client.post(
        "/api/v1/auth/dev-login",
        json={"email": "dev@example.com", "password": "dev-password"},
    )
    assert response.status_code == 404
