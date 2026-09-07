"""ProfilesRepo.ensure — recreating a missing row after a DB wipe."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.profiles_repo import ProfilesRepo


def _profile_row(*, is_approved: bool = False, is_admin: bool = False) -> MagicMock:
    row = MagicMock()
    row._mapping = {
        "id": "u1",
        "is_admin": is_admin,
        "is_approved": is_approved,
        "max_active_personas": 5,
        "nick": None,
        "usage_budget_usd": 10.0,
        "created_at": datetime.now(UTC),
    }
    return row


async def _execute_with_insert(
    calls: list[str],
    insert_params: dict[str, Any],
    *,
    is_approved: bool,
) -> Any:
    async def execute(statement: Any, params: dict[str, Any] | None = None) -> MagicMock:
        sql = str(statement)
        calls.append(sql)
        result = MagicMock()
        if "INSERT INTO profiles" in sql:
            if params:
                insert_params.update(params)
            return result
        result.one_or_none = MagicMock(return_value=_profile_row(is_approved=is_approved))
        return result

    return execute


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


@pytest.mark.asyncio
async def test_ensure_inserts_unapproved_for_non_admin_email() -> None:
    calls: list[str] = []
    insert_params: dict[str, Any] = {}
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=await _execute_with_insert(calls, insert_params, is_approved=False))

    repo = ProfilesRepo(conn)
    profile = await repo.ensure("u1", email="new.user@example.com")

    insert_sql = next(c for c in calls if "INSERT INTO profiles" in c)
    assert "is_approved" in insert_sql
    assert insert_params["is_approved"] is False
    assert "ON CONFLICT (id) DO NOTHING" in insert_sql
    assert profile.is_approved is False


@pytest.mark.asyncio
async def test_ensure_inserts_approved_for_admin_email() -> None:
    calls: list[str] = []
    insert_params: dict[str, Any] = {}
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=await _execute_with_insert(calls, insert_params, is_approved=True))

    repo = ProfilesRepo(conn)
    profile = await repo.ensure("u1", email="fmazurkiewicz@gmail.com")

    insert_sql = next(c for c in calls if "INSERT INTO profiles" in c)
    assert insert_params["is_approved"] is True
    assert "ON CONFLICT (id) DO NOTHING" in insert_sql
    assert profile.is_approved is True


@pytest.mark.asyncio
async def test_ensure_does_not_update_is_approved_on_conflict() -> None:
    calls: list[str] = []
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=await _execute_with_insert(calls, {}, is_approved=False))

    repo = ProfilesRepo(conn)
    await repo.ensure("u1", email="fmazurkiewicz@gmail.com")

    assert not any("UPDATE profiles" in c for c in calls)


@pytest.mark.asyncio
async def test_update_is_approved_returns_updated_row() -> None:
    conn = AsyncMock()
    result = MagicMock()
    result.one_or_none = MagicMock(return_value=_profile_row(is_approved=True))
    conn.execute = AsyncMock(return_value=result)

    repo = ProfilesRepo(conn)
    profile = await repo.update_is_approved("u1", True)

    sql = str(conn.execute.await_args.args[0])
    assert "UPDATE profiles SET is_approved" in sql
    assert "usage_budget_usd" not in sql.split("SET")[1].split("WHERE")[0]
    assert profile.is_approved is True
    assert profile.usage_budget_usd == 10.0
