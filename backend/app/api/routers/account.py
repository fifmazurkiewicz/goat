"""Router `/account` — ustawienia konta (nick, ADR-15), OSOBNE od `/profile` (biometria).

Cienki: odczyt/zapis nicka w kontekście RLS własnego usera. Brakujący wiersz `profiles`
(np. po wipe public bez ponownego seeda) jest uzupełniany przez `service_role` —
authenticated nie ma policy INSERT na `profiles`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.db import rls_connection, service_role_connection
from app.core.security import AuthContext, get_current_user
from app.models.schemas import AccountOut, AccountUpdate
from app.repositories.profiles_repo import ProfilesRepo

router = APIRouter(prefix="/account", tags=["account"])


@router.get("", response_model=AccountOut)
@router.get("/", response_model=AccountOut, include_in_schema=False)
async def get_account(auth: AuthContext = Depends(get_current_user)) -> AccountOut:
    async with rls_connection(auth.claims) as conn:
        profile = await ProfilesRepo(conn).get(auth.user_id)
    if profile is None:
        async with service_role_connection() as conn:
            profile = await ProfilesRepo(conn).ensure(auth.user_id)
    return AccountOut.model_validate(profile)


@router.patch("", response_model=AccountOut)
@router.patch("/", response_model=AccountOut, include_in_schema=False)
async def update_account(
    payload: AccountUpdate, auth: AuthContext = Depends(get_current_user)
) -> AccountOut:
    # ensure przez service_role (brak INSERT policy dla authenticated), potem UPDATE
    # własnego nicka — `auth.user_id` z JWT, nigdy z body.
    async with service_role_connection() as conn:
        repo = ProfilesRepo(conn)
        await repo.ensure(auth.user_id)
        profile = await repo.update_nick(auth.user_id, payload.nick)
    return AccountOut.model_validate(profile)
