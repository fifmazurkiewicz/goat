"""Router `/exercises` — katalog ćwiczeń referencyjnych (ADR-14).

Cienki: filtrowanie to proste `WHERE` w `ExercisesRepo`, bez własnego `domain/exercises/`
(zgodnie z ADR-14 — to czysta treść referencyjna, nie logika biznesowa).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.config import settings
from app.core.db import rls_connection
from app.core.security import AuthContext, get_current_user
from app.models.schemas import ExerciseOut, PersonaType
from app.repositories.exercises_repo import ExerciseRow, ExercisesRepo

EXERCISE_PHOTOS_BUCKET = "exercise-photos"


def public_photo_url(photo_path: str | None) -> str | None:
    """Ścieżka w buckecie → publiczny URL Storage. Pełny URL (stary seed) zostaje."""
    if not photo_path:
        return None
    if photo_path.startswith("http://") or photo_path.startswith("https://"):
        return photo_path
    base = (settings.supabase_url or "").rstrip("/")
    if not base:
        return photo_path
    return f"{base}/storage/v1/object/public/{EXERCISE_PHOTOS_BUCKET}/{photo_path.lstrip('/')}"


def _to_out(row: ExerciseRow) -> ExerciseOut:
    # `id` jest `uuid` w DB (asyncpg/SQLAlchemy zwraca UUID, nie str). Konwersja w DTO,
    # nie w repo — spójnie z resztą endpointów (AGENTS.md: "asyncpg: UUID→str w DTO").
    return ExerciseOut(
        id=str(row.id),
        slug=row.slug,
        name=row.name,
        name_en=row.name_en,
        persona_type=row.persona_type,  # type: ignore[arg-type]
        level=row.level,  # type: ignore[arg-type]
        categories=row.categories,
        short_description=row.short_description,
        detail_full=row.detail_full,
        common_mistakes=row.common_mistakes,
        photo_path=public_photo_url(row.photo_path),
    )

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("", response_model=list[ExerciseOut])
@router.get("/", response_model=list[ExerciseOut], include_in_schema=False)
async def list_exercises(
    persona_type: PersonaType | None = Query(default=None),
    category: str | None = Query(default=None),
    query: str | None = Query(default=None, max_length=100),
    auth: AuthContext = Depends(get_current_user),
) -> list[ExerciseOut]:
    async with rls_connection(auth.claims) as conn:
        rows = await ExercisesRepo(conn).list_all(
            persona_type=persona_type, category=category, query=query
        )
    return [_to_out(row) for row in rows]
