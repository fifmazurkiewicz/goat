"""`/exercises` router — reference exercise catalog (ADR-14).

Thin: filtering is a simple `WHERE` in `ExercisesRepo`, without its own
`domain/exercises/` (per ADR-14 — this is pure reference content, not business logic).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.config import settings
from app.core.db import rls_connection
from app.core.security import AuthContext, get_current_user
from app.models.schemas import ExerciseOut, PersonaType
from app.repositories.exercises_repo import ExerciseRow, ExercisesRepo

EXERCISE_PHOTOS_BUCKET = "exercise-photos"
# Inner folder inside the bucket (manual upload layout in Supabase Storage).
PHOTO_STORAGE_ROOT = "exercise-photos"


def bucket_object_path(photo_path: str) -> str:
    """DB path (`free-exercise-db/<Id>/0.jpg`) -> object key inside the bucket."""
    path = photo_path.lstrip("/")
    if path.startswith(f"{PHOTO_STORAGE_ROOT}/"):
        return path
    return f"{PHOTO_STORAGE_ROOT}/{path}"


def public_photo_url(photo_path: str | None) -> str | None:
    """Bucket path -> public Storage URL. Full URL (old seed) is passed through."""
    if not photo_path:
        return None
    if photo_path.startswith("http://") or photo_path.startswith("https://"):
        return photo_path
    base = (settings.supabase_url or "").rstrip("/")
    object_path = bucket_object_path(photo_path)
    if not base:
        return object_path
    return f"{base}/storage/v1/object/public/{EXERCISE_PHOTOS_BUCKET}/{object_path}"


def _to_out(row: ExerciseRow) -> ExerciseOut:
    # `id` is `uuid` in DB (asyncpg/SQLAlchemy returns UUID, not str). Conversion in the
    # DTO, not in the repo — consistent with the other endpoints (AGENTS.md:
    # "asyncpg: UUID->str in DTO").
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
