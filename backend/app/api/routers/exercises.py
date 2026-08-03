"""Router `/exercises` — katalog ćwiczeń referencyjnych (ADR-14).

Cienki: filtrowanie to proste `WHERE` w `ExercisesRepo`, bez własnego `domain/exercises/`
(zgodnie z ADR-14 — to czysta treść referencyjna, nie logika biznesowa).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.db import rls_connection
from app.core.security import AuthContext, get_current_user
from app.models.schemas import ExerciseOut, PersonaType
from app.repositories.exercises_repo import ExercisesRepo

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("/", response_model=list[ExerciseOut])
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
    return [ExerciseOut.model_validate(row) for row in rows]
