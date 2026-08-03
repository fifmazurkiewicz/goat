"""Router `/plans` — generowanie i odczyt planów (pipeline 3-etapowy, `BackgroundTasks`).

Patrz docs/technical/architecture.md sekcja 4 (pipeline, model stanu jobów) i
docs/adr/decisions.md ADR-1/ADR-2. Orkiestracja w
`app/domain/plans/orchestrator.py::PlanOrchestrator`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import AuthContext, get_current_user

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/")
async def list_plans(auth: AuthContext = Depends(get_current_user)) -> list[dict]:
    # TODO: pełna implementacja — patrz docs/technical/architecture.md.
    return []


# TODO: `POST /plans/generate` (kolejkuje BackgroundTasks + zwraca job_id) i
# `GET /plans/jobs/{id}` (pollowany przez frontend, breakdown per-persona,
# obsługa partial_success) — patrz architecture.md sekcja 4.
