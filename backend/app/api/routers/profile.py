"""Router `/profile` — fallback formularz dla `user_profile` (ADR-11, ai-pipeline.md §0).

Ścieżka alternatywna do głównej, konwersacyjnej ("persona dopytuje w czacie", narzędzie
`update_user_profile` — patrz `app/domain/chat/tools.py`) dla userów wolących wypełnić
dane wprost. Obie ścieżki piszą do tej samej tabeli przez `UserProfileRepo.upsert`.

Router CIENKI — logika (merge częściowej aktualizacji z istniejącym wierszem) docelowo
w `app/domain/personas/service.py`-analogicznym serwisie profilu, nie tutaj.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import AuthContext, get_current_user
from app.models.schemas import UserProfileOut, UserProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/", response_model=UserProfileOut | None)
async def get_profile(auth: AuthContext = Depends(get_current_user)) -> UserProfileOut | None:
    # TODO: rls_connection(auth.claims) -> UserProfileRepo(conn).get(auth.user_id).
    # `None` (profil jeszcze nieutworzony) jest poprawną odpowiedzią — frontend renderuje
    # pusty formularz, nie błąd.
    return None


@router.patch("/", response_model=UserProfileOut)
async def update_profile(
    payload: UserProfileUpdate, auth: AuthContext = Depends(get_current_user)
) -> UserProfileOut:
    # TODO: rls_connection(auth.claims) -> UserProfileRepo(conn).upsert(
    #   auth.user_id, payload.model_dump(exclude_unset=True)
    # ) w jednej transakcji, zmapować UserProfileRow -> UserProfileOut.
    raise NotImplementedError(
        "update_profile — do zaimplementowania w etapie profilu użytkownika, patrz "
        "docs/technical/ai-pipeline.md sekcja 0."
    )
