"""Shared fixtures for backend tests.

Env placeholders are set *before* importing `app.main` because `Settings` initializes
at module import time and requires `DATABASE_URL` / `SUPABASE_*` / `OPENROUTER_API_KEY`.
The values don't need to be real — unit tests don't connect to DB/OpenRouter.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

# Must be before `from app.main import app` — Settings initializes at module level.
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
os.environ.setdefault("DEV_AUTH_EMAIL", "dev@example.com")
os.environ.setdefault("DEV_AUTH_PASSWORD", "dev-password")

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac