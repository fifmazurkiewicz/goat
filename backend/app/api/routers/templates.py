"""Templates router — `GET /persona-templates` and `GET /plan-templates`.

Read-only tables (public RLS SELECT). Endpoints require auth, so the catalog isn't
exposed without a session; reads go via `rls_connection` like the rest of the API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.db import rls_connection
from app.core.security import AuthContext, get_current_user, require_approved
from app.models.schemas import PersonaTemplateOut, PlanTemplateOut
from app.repositories.templates_repo import PersonaTemplatesRepo, PlanTemplatesRepo

router = APIRouter(tags=["templates"], dependencies=[Depends(require_approved)])


@router.get("/persona-templates", response_model=list[PersonaTemplateOut])
async def list_persona_templates(
    auth: AuthContext = Depends(get_current_user),
) -> list[PersonaTemplateOut]:
    async with rls_connection(auth.claims) as conn:
        rows = await PersonaTemplatesRepo(conn).list_all()
    return [PersonaTemplateOut.model_validate(row) for row in rows]


@router.get("/plan-templates", response_model=list[PlanTemplateOut])
async def list_plan_templates(
    auth: AuthContext = Depends(get_current_user),
) -> list[PlanTemplateOut]:
    async with rls_connection(auth.claims) as conn:
        rows = await PlanTemplatesRepo(conn).list_all()
    return [PlanTemplateOut.model_validate(row) for row in rows]
