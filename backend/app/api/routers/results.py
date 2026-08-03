"""Router `/results` — wyniki logowane przez agenta (tool calling) lub ręcznie.

Patrz docs/technical/database-schema.md (tabela `results`) i docs/adr/decisions.md
ADR-9 (wykresy trendu per metryka we `/results`, bez zmian schematu poza indeksem
`results_user_category_metric_date`).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import AuthContext, get_current_user

router = APIRouter(prefix="/results", tags=["results"])


@router.get("/")
async def list_results(auth: AuthContext = Depends(get_current_user)) -> list[dict]:
    # TODO: pełna implementacja — patrz docs/technical/architecture.md.
    return []
