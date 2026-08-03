"""Router `/account` — ustawienia konta (nick, ADR-15), OSOBNE od `/profile` (biometria).

Cienki: `ProfilesRepo` w kontekście RLS własnego usera (nie `service_role` — to nie
`/admin/*`, user zarządza WYŁĄCZNIE swoim kontem).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.db import rls_connection
from app.core.security import AuthContext, get_current_user
from app.models.schemas import AccountOut, AccountUpdate
from app.repositories.profiles_repo import ProfilesRepo

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/", response_model=AccountOut)
async def get_account(auth: AuthContext = Depends(get_current_user)) -> AccountOut:
    async with rls_connection(auth.claims) as conn:
        profile = await ProfilesRepo(conn).get(auth.user_id)
    # `profiles` ma wiersz od rejestracji (trigger `handle_new_user`) — brak wiersza
    # oznaczałby niespójny stan konta, nie normalną ścieżkę "jeszcze nieuzupełnione".
    if profile is None:
        return AccountOut(id=auth.user_id, nick=None, is_admin=False)
    return AccountOut.model_validate(profile)


@router.patch("/", response_model=AccountOut)
async def update_account(
    payload: AccountUpdate, auth: AuthContext = Depends(get_current_user)
) -> AccountOut:
    async with rls_connection(auth.claims) as conn:
        profile = await ProfilesRepo(conn).update_nick(auth.user_id, payload.nick)
    return AccountOut.model_validate(profile)
