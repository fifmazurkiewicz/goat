"""Kontrakt `GET /exercises` — `common_mistakes` nullable (import free-exercise-db, 2026-08-23).

Import ~868 ćwiczeń z yuhonas/free-exercise-db (Unlicense) ma `common_mistakes = NULL`
(dataset nie zawiera tej treści — nie zmyślamy porad technicznych). Regresja, którą łapie
ten test: bez `str | None` w `ExerciseOut` FastAPI wywaliłby się na walidacji albo FE
(types/api.ts) kłamałby typem `string`, a sekcja „Częste błędy" renderowałaby pusty tekst.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _exercise_row(*, slug: str, common_mistakes: str | None) -> MagicMock:
    row = MagicMock()
    row.id = f"id-{slug}"
    row.slug = slug
    row.name = "Przysiad ze sztangą"
    row.name_en = "Barbell Squat"
    row.persona_type = "motor_coach"
    row.level = "intermediate"
    row.categories = ["Uda", "Siłowe"]
    row.short_description = "Krótki opis."
    row.detail_full = "Instrukcja wykonania."
    row.common_mistakes = common_mistakes
    row.photo_path = None
    return row


@pytest.fixture
def _patched(monkeypatch: pytest.MonkeyPatch):
    """Fake repo + RLS + auth dla routera list_exercises."""

    @asynccontextmanager
    async def fake_rls(_claims: object):
        yield MagicMock()

    class FakeExercisesRepo:
        def __init__(self, _conn: object) -> None:
            pass

        async def list_all(self, **_kwargs: object):
            return [
                # Importowany z datasetu — brak treści "Częste błędy".
                _exercise_row(slug="barbell-squat", common_mistakes=None),
                # Ręczny wpis kuratorowany — wartość obecna.
                _exercise_row(slug="serw-krotki-technika", common_mistakes="Zbyt duży zamach."),
            ]

    monkeypatch.setattr("app.api.routers.exercises.rls_connection", fake_rls)
    monkeypatch.setattr("app.api.routers.exercises.ExercisesRepo", FakeExercisesRepo)

    async def fake_auth() -> object:
        ctx = MagicMock()
        ctx.claims = {"sub": "u1"}
        ctx.user_id = "u1"
        return ctx

    from app.core.security import get_current_user
    app.dependency_overrides[get_current_user] = fake_auth
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_exercises_endpoint_serializes_null_common_mistakes(_patched) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/exercises")
    assert res.status_code == 200
    exercises = res.json()
    imported = next(e for e in exercises if e["slug"] == "barbell-squat")
    assert imported["common_mistakes"] is None
    assert imported["name"] == "Przysiad ze sztangą"
    assert imported["name_en"] == "Barbell Squat"
    manual = next(e for e in exercises if e["slug"] == "serw-krotki-technika")
    assert manual["common_mistakes"] == "Zbyt duży zamach."
