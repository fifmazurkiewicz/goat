"""ProfilesRepo.ensure — odtwarzanie brakującego wiersza po wipe DB."""

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


class _SelectThenEnsure:
    """Pierwsze execute = INSERT ensure, drugie = SELECT get."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __call__(self, statement: Any, params: dict[str, Any] | None = None) -> MagicMock:
        sql = str(statement)
        self.calls.append(sql)
        result = MagicMock()
        if "INSERT INTO profiles" in sql:
            result.one_or_none = MagicMock(return_value=None)
            return result
        result.one_or_none = MagicMock(return_value=_profile_row())
        return result


@pytest.mark.asyncio
async def test_ensure_inserts_missing_profile() -> None:
    conn = AsyncMock()
    tracker = _SelectThenEnsure()
    conn.execute = AsyncMock(side_effect=tracker)

    repo = ProfilesRepo(conn)
    profile = await repo.ensure("u1")

    assert profile.id == "u1"
    assert any("INSERT INTO profiles" in c for c in tracker.calls)
    assert any("SELECT" in c and "FROM profiles" in c for c in tracker.calls)
