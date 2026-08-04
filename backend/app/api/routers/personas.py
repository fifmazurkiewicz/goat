"""Router `/personas` — CIENKI: parsing requestu + wywołanie `PersonaService`.

Cała logika (limit aktywnych per konto — ADR-12, merge kolumn, moderacja przy create/edit/share)
żyje w `app/domain/personas/service.py` i `app/domain/moderation/service.py` —
patrz docs/technical/architecture.md sekcja 1.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.db import rls_connection, service_role_connection
from app.core.dependencies import get_moderation_service
from app.core.security import AuthContext, get_current_user
from app.domain.personas.service import PersonaService
from app.models.schemas import (
    PersonaCreate,
    PersonaOut,
    PersonasListOut,
    PersonaShareUpdate,
    PersonaUpdate,
)
from app.repositories.personas_repo import PersonasRepo
from app.repositories.profiles_repo import DEFAULT_MAX_ACTIVE_PERSONAS, ProfilesRepo

router = APIRouter(prefix="/personas", tags=["personas"])


@router.get("", response_model=PersonasListOut)
@router.get("/", response_model=PersonasListOut, include_in_schema=False)
async def list_personas(auth: AuthContext = Depends(get_current_user)) -> PersonasListOut:
    async with rls_connection(auth.claims) as conn:
        profiles_repo = ProfilesRepo(conn)
        service = PersonaService(PersonasRepo(conn), profiles_repo, get_moderation_service())
        rows = await service.list_own(auth.user_id)
        profile = await profiles_repo.get(auth.user_id)
    return PersonasListOut(
        items=[PersonaOut.model_validate(row) for row in rows],
        max_active_personas=(
            profile.max_active_personas if profile is not None else DEFAULT_MAX_ACTIVE_PERSONAS
        ),
    )


@router.get("/community", response_model=list[PersonaOut])
async def list_community_personas(auth: AuthContext = Depends(get_current_user)) -> list[PersonaOut]:
    async with rls_connection(auth.claims) as conn:
        service = PersonaService(PersonasRepo(conn), ProfilesRepo(conn), get_moderation_service())
        rows = await service.list_community(auth.user_id)
    return [PersonaOut.model_validate(row) for row in rows]


@router.get("/{persona_id}", response_model=PersonaOut)
async def get_persona(persona_id: str, auth: AuthContext = Depends(get_current_user)) -> PersonaOut:
    async with rls_connection(auth.claims) as conn:
        service = PersonaService(PersonasRepo(conn), ProfilesRepo(conn), get_moderation_service())
        row = await service.get_persona(persona_id, auth.user_id)
    return PersonaOut.model_validate(row)


@router.post("", response_model=PersonaOut, status_code=201)
@router.post("/", response_model=PersonaOut, status_code=201, include_in_schema=False)
async def create_persona(
    payload: PersonaCreate, auth: AuthContext = Depends(get_current_user)
) -> PersonaOut:
    # Trigger `enforce_persona_limit` czyta `profiles.max_active_personas` — brak wiersza
    # po wipe DB dawałby NULL/5, ale limit API też opiera się o profil; ensure = spójny stan.
    async with service_role_connection() as conn:
        await ProfilesRepo(conn).ensure(auth.user_id)
    async with rls_connection(auth.claims) as conn:
        service = PersonaService(PersonasRepo(conn), ProfilesRepo(conn), get_moderation_service())
        row = await service.create_persona(auth.user_id, payload.model_dump())
    return PersonaOut.model_validate(row)


@router.patch("/{persona_id}", response_model=PersonaOut)
async def update_persona(
    persona_id: str, payload: PersonaUpdate, auth: AuthContext = Depends(get_current_user)
) -> PersonaOut:
    async with rls_connection(auth.claims) as conn:
        service = PersonaService(PersonasRepo(conn), ProfilesRepo(conn), get_moderation_service())
        row = await service.update_persona(
            persona_id, auth.user_id, payload.model_dump(exclude_unset=True)
        )
    return PersonaOut.model_validate(row)


@router.delete("/{persona_id}", status_code=204)
async def delete_persona(persona_id: str, auth: AuthContext = Depends(get_current_user)) -> None:
    async with rls_connection(auth.claims) as conn:
        service = PersonaService(PersonasRepo(conn), ProfilesRepo(conn), get_moderation_service())
        await service.delete_persona(persona_id, auth.user_id)


@router.patch("/{persona_id}/share", response_model=PersonaOut)
async def share_persona(
    persona_id: str, payload: PersonaShareUpdate, auth: AuthContext = Depends(get_current_user)
) -> PersonaOut:
    async with rls_connection(auth.claims) as conn:
        service = PersonaService(PersonasRepo(conn), ProfilesRepo(conn), get_moderation_service())
        row = await service.share_persona(persona_id, auth.user_id, payload.is_shared)
    return PersonaOut.model_validate(row)


@router.post("/{persona_id}/clone", response_model=PersonaOut, status_code=201)
async def clone_persona(persona_id: str, auth: AuthContext = Depends(get_current_user)) -> PersonaOut:
    async with rls_connection(auth.claims) as conn:
        service = PersonaService(PersonasRepo(conn), ProfilesRepo(conn), get_moderation_service())
        row = await service.clone_persona(persona_id, auth.user_id)
    return PersonaOut.model_validate(row)
