from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import HealthConsentRequiredError
from app.core.security import AuthContext, require_health_consent
from app.repositories.privacy_repo import HEALTH_CONSENT_VERSION, PrivacyRepo


@pytest.mark.asyncio
async def test_health_consent_gate_rejects_missing_consent(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ConnectionContext:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr("app.core.security.service_role_connection", _ConnectionContext)
    monkeypatch.setattr(PrivacyRepo, "active_consents", AsyncMock(return_value={}))
    with pytest.raises(HealthConsentRequiredError):
        await require_health_consent(AuthContext(user_id="u1"))


@pytest.mark.asyncio
async def test_health_consent_gate_accepts_active_consent(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ConnectionContext:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr("app.core.security.service_role_connection", _ConnectionContext)
    monkeypatch.setattr(
        PrivacyRepo,
        "active_consents",
        AsyncMock(return_value={"health_data": {"version": HEALTH_CONSENT_VERSION}}),
    )
    auth = AuthContext(user_id="u1")
    assert await require_health_consent(auth) is auth


@pytest.mark.asyncio
async def test_health_consent_gate_rejects_stale_version(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ConnectionContext:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr("app.core.security.service_role_connection", _ConnectionContext)
    monkeypatch.setattr(
        PrivacyRepo,
        "active_consents",
        AsyncMock(return_value={"health_data": {"version": "health-v0"}}),
    )
    with pytest.raises(HealthConsentRequiredError):
        await require_health_consent(AuthContext(user_id="u1"))


@pytest.mark.asyncio
async def test_supabase_admin_delete_user_calls_auth_admin_endpoint() -> None:
    from app.core.supabase_admin import SupabaseAdminClient

    client = SupabaseAdminClient()
    response = MagicMock(status_code=204)
    client._client = AsyncMock()
    client._client.delete.return_value = response
    await client.delete_user("user-1")
    client._client.delete.assert_awaited_once_with("/users/user-1")
