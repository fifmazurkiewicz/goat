"""`/account` router — account settings (nick, ADR-15), SEPARATE from `/profile` (biometrics).

Thin: read/write of the nick in the user's own RLS context. A missing `profiles`
row (e.g. after a public wipe without re-seeding) is backfilled via `service_role` —
authenticated doesn't have an INSERT policy on `profiles`. GET is ungated so the
waiting screen can poll `is_approved` (ADR-22); PATCH requires approval.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.approval import email_from_claims
from app.core.db import rls_connection, service_role_connection
from app.core.security import AuthContext, get_current_user, require_approved
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
            profile = await ProfilesRepo(conn).ensure(
                auth.user_id, email=email_from_claims(auth.claims)
            )
    return AccountOut.model_validate(profile)


@router.patch("", response_model=AccountOut)
@router.patch("/", response_model=AccountOut, include_in_schema=False)
async def update_account(
    payload: AccountUpdate, auth: AuthContext = Depends(require_approved)
) -> AccountOut:
    # ensure via service_role (no INSERT policy for authenticated), then UPDATE of
    # the user's own nick — `auth.user_id` from the JWT, never from the body.
    async with service_role_connection() as conn:
        repo = ProfilesRepo(conn)
        await repo.ensure(auth.user_id, email=email_from_claims(auth.claims))
        profile = await repo.update_nick(auth.user_id, payload.nick)
    return AccountOut.model_validate(profile)
