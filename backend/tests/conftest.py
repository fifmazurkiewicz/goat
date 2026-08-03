"""Fixture'y współdzielone dla testów backendu.

Wymaga obecności `backend/.env` (ładowanego przez `pydantic-settings`) — pola typu
`database_url`/`supabase_url`/`openrouter_api_key` nie mają defaultów (patrz
`app/core/config.py`), placeholdery z `.env.example` wystarczają dla tego testu, bo
`/api/health` nie dotyka bazy ani zewnętrznych usług.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
