"""Router `/personas` — CIENKI: parsing requestu + wywołanie `PersonaService`.

Cała logika (limit aktywnych per konto — ADR-12, merge kolumn, moderacja przy create/edit/share)
żyje w `app/domain/personas/service.py` i `app/domain/moderation/service.py` —
patrz docs/technical/architecture.md sekcja 1.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import AuthContext, get_current_user
from app.models.schemas import PersonaOut

router = APIRouter(prefix="/personas", tags=["personas"])


@router.get("/", response_model=list[PersonaOut])
async def list_personas(auth: AuthContext = Depends(get_current_user)) -> list[PersonaOut]:
    # TODO: pełna implementacja — patrz docs/technical/architecture.md.
    # Docelowo: otworzyć app.core.db.rls_connection(auth.claims), zawołać
    # PersonasRepo(conn).list_for_user(auth.user_id), zmapować na PersonaOut.
    return []
