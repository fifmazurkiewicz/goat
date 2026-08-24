"""ProfilesRepo.ensure — recreating a missing row after a DB wipe."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.profiles_repo import ProfilesRepo


def _profile_row() -> MagicMock:
    row = MagicMock()
    row._mapping = {
        "id": "u1",
        "is_admin": False,
        "max_active_personas": 5,
        "nick": None,
        "usage_budget_usd": 10.0,
        "created_at": datetime.now(timezone.utc),
    }
    return row


@pytest.mark.asyncio
async def test_ensure_inserts_missing_profile() -> None:
    calls: list[str] = []

    async def execute(statement: Any, params: dict[str, Any] | None = None) -> MagicMock:
        sql = str(statement)
        calls.append(sql)
        result = MagicMock()
        if "INSERT INTO profiles" in sql:
            return result
        result.one_or_none = MagicMock(return_value=_profile_row())
        return result

    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=execute)

    repo = ProfilesRepo(conn)
    profile = await repo.ensure("u1")

    assert profile.id == "u1"
    assert any("INSERT INTO profiles" in c for c in calls)
    assert any("SELECT" in c and "FROM profiles" in c for c in calls)