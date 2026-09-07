"""Contract for `GET /exercises` — `common_mistakes` nullable (free-exercise-db import, 2026-08-23).

The import of ~868 exercises from yuhonas/free-exercise-db (Unlicense) has
`common_mistakes = NULL` (the dataset lacks this content — we don't fabricate technical tips).
Regression this test catches: without `str | None` in `ExerciseOut` FastAPI would crash on
validation, or the FE (types/api.ts) would lie about the `string` type and the "Common mistakes"
section would render empty text.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.routers.exercises import bucket_object_path, public_photo_url
from app.main import app


def _exercise_row(*, slug: str, common_mistakes: str | None, raw_id: object) -> MagicMock:
    row = MagicMock()
    row.id = raw_id
    row.slug = slug
    row.name = "Przysiad ze sztangą"
    row.name_en = "Barbell Squat"
    row.persona_type = "motor_coach"
    row.level = "intermediate"
    row.categories = ["Uda", "Siłowe"]
    row.short_description = "Krótki opis."
    row.detail_full = "Instrukcja wykonania."
    row.common_mistakes = common_mistakes
    row.photo_path = "free-exercise-db/Barbell_Squat/0.jpg"
    row.photo_path_2 = "free-exercise-db/Barbell_Squat/1.jpg"
    return row


@pytest.fixture
def _patched(monkeypatch: pytest.MonkeyPatch):
    """Fake repo + RLS + auth for the list_exercises router."""

    @asynccontextmanager
    async def fake_rls(_claims: object):
        yield MagicMock()

    class FakeExercisesRepo:
        def __init__(self, _conn: object) -> None:
            pass

        async def list_all(self, **_kwargs: object):
            return [
                # Imported from the dataset — no "Common mistakes" content.
                _exercise_row(
                    slug="barbell-squat",
                    common_mistakes=None,
                    # Simulation of a real `uuid` column in DB — asyncpg/SQLAlchemy
                    # return UUID, not str. Conversion must work in `_to_out`,
                    # otherwise Pydantic raises ValidationError and the endpoint returns
                    # 500 with masked body (handle_unexpected_error). Regression from 2026-08-24.
                    raw_id=UUID("f9c6dcdc-f3f6-4134-8aae-f6908ffb49ac"),
                ),
                # Manually curated entry — value present, classic string-id.
                _exercise_row(
                    slug="serw-krotki-technika",
                    common_mistakes="Zbyt duży zamach.",
                    raw_id="id-custom-1",
                ),
            ]

    monkeypatch.setattr("app.api.routers.exercises.rls_connection", fake_rls)
    monkeypatch.setattr("app.api.routers.exercises.ExercisesRepo", FakeExercisesRepo)
    monkeypatch.setattr(
        "app.api.routers.exercises.settings.supabase_url",
        "https://example.supabase.co",
    )

    async def fake_auth() -> object:
        ctx = MagicMock()
        ctx.claims = {"sub": "u1"}
        ctx.user_id = "u1"
        return ctx

    from app.core.security import get_current_user, require_approved
    app.dependency_overrides[get_current_user] = fake_auth
    app.dependency_overrides[require_approved] = fake_auth
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_approved, None)


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
    assert str(imported["photo_path"]).endswith(
        "exercise/free-exercise-db/Barbell_Squat/0.jpg"
    )
    assert str(imported["photo_path_2"]).endswith(
        "exercise/free-exercise-db/Barbell_Squat/1.jpg"
    )
    # UUID from DB must be serialized as a string in JSON, not thrown at the client.
    assert imported["id"] == "f9c6dcdc-f3f6-4134-8aae-f6908ffb49ac"
    assert isinstance(imported["id"], str)
    manual = next(e for e in exercises if e["slug"] == "serw-krotki-technika")
    assert manual["common_mistakes"] == "Zbyt duży zamach."
    assert manual["id"] == "id-custom-1"


def test_bucket_object_path_adds_inner_folder() -> None:
    assert (
        bucket_object_path("free-exercise-db/Barbell_Squat/0.jpg")
        == "exercise/free-exercise-db/Barbell_Squat/0.jpg"
    )
    assert (
        bucket_object_path("exercise/free-exercise-db/Barbell_Squat/0.jpg")
        == "exercise/free-exercise-db/Barbell_Squat/0.jpg"
    )
    # Legacy inner folder name remapped to `exercise/`.
    assert (
        bucket_object_path("exercise-photos/free-exercise-db/Barbell_Squat/0.jpg")
        == "exercise/free-exercise-db/Barbell_Squat/0.jpg"
    )


def test_public_photo_url_keeps_absolute_and_prefixes_relative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.routers.exercises.settings.supabase_url",
        "https://example.supabase.co",
    )
    assert public_photo_url(None) is None
    assert public_photo_url("https://cdn.example/a.jpg") == "https://cdn.example/a.jpg"
    relative = public_photo_url("free-exercise-db/Barbell_Squat/0.jpg")
    assert relative is not None
    assert relative.endswith("exercise/free-exercise-db/Barbell_Squat/0.jpg")