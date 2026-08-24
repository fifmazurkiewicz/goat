"""PersonasRepo — CAST jsonb on create/update (asyncpg + text())."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.personas_repo import PersonasRepo


class _FakeResult:
    def __init__(self, row: Any) -> None:
        self._row = row

    def one(self) -> Any:
        return self._row

    def one_or_none(self) -> Any:
        return self._row


def _fake_row(**overrides: Any) -> MagicMock:
    from datetime import datetime, timezone

    base = {
        "id": "p1",
        "user_id": "u1",
        "type": "dietitian",
        "name": "Dietetyk",
        "system_prompt": "prompt",
        "base_template_id": None,
        "plan_template_id": None,
        "template_overrides": {"columns": ["Kolumna 1"]},
        "detail_level": "simple",
        "custom_result_category": None,
        "persona_constraints": None,
        "slug": "dietitian_dietetyk",
        "is_shared": False,
        "moderation_status": "approved",
        "moderation_checked_prompt_hash": "abc",
        "preamble_version": 2,
        "cloned_from_persona_id": None,
        "active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    base.update(overrides)
    row = MagicMock()
    row._mapping = base
    return row


@pytest.mark.asyncio
async def test_create_casts_template_overrides_as_jsonb() -> None:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=_FakeResult(_fake_row()))
    repo = PersonasRepo(conn)

    await repo.create(
        "u1",
        {
            "type": "dietitian",
            "name": "Dietetyk",
            "system_prompt": "Jesteś dietetykiem sportowym w aplikacji Coach.",
            "template_overrides": {"columns": ["Kolumna 1"]},
            "slug": "dietitian_dietetyk",
            "moderation_status": "approved",
            "moderation_checked_prompt_hash": "abc",
            "preamble_version": 2,
        },
    )

    sql = str(conn.execute.await_args.args[0])
    params = conn.execute.await_args.args[1]
    assert "CAST(:template_overrides AS jsonb)" in sql
    assert params["template_overrides"] == json.dumps({"columns": ["Kolumna 1"]})


@pytest.mark.asyncio
async def test_update_casts_template_overrides_as_jsonb() -> None:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=_FakeResult(_fake_row()))
    repo = PersonasRepo(conn)

    await repo.update("p1", "u1", {"template_overrides": {"columns": ["Posiłek", "Kcal"]}})

    sql = str(conn.execute.await_args.args[0])
    params = conn.execute.await_args.args[1]
    assert "template_overrides = CAST(:template_overrides AS jsonb)" in sql
    assert params["template_overrides"] == json.dumps({"columns": ["Posiłek", "Kcal"]})