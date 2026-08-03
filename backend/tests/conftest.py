"""Fixture'y współdzielone dla testów backendu.

Placeholdery env są ustawiane *przed* importem `app.main`, bo `Settings` ładuje się
przy imporcie modułu i wymaga `DATABASE_URL` / `SUPABASE_*` / `OPENROUTER_API_KEY`.
Wartości nie muszą być prawdziwe — testy jednostkowe nie łączą się z DB/OpenRouter.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

# Musi być przed `from app.main import app` — Settings inicjalizuje się na poziomie modułu.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/postgres",
)
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault(
    "SUPABASE_JWKS_URL",
    "https://example.supabase.co/auth/v1/.well-known/jwks.json",
)
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
