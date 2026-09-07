"""`/profile` router — form fallback for `user_profile` (ADR-11, ai-pipeline.md §0).

Alternative path to the main, conversational one ("persona asks in the chat", tool
`update_user_profile` — see `app/domain/chat/tools.py`) for users who prefer to fill
in their data directly. Both paths write to the same table via `UserProfileRepo.upsert`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.db import rls_connection
from app.core.exceptions import ValidationError
from app.core.security import AuthContext, get_current_user, require_approved
from app.models.schemas import UserProfileOut, UserProfileUpdate
from app.repositories.user_profile_repo import UserProfileRepo

router = APIRouter(
    prefix="/profile",
    tags=["profile"],
    dependencies=[Depends(require_approved)],
)


@router.get("", response_model=UserProfileOut | None)
@router.get("/", response_model=UserProfileOut | None, include_in_schema=False)
async def get_profile(auth: AuthContext = Depends(get_current_user)) -> UserProfileOut | None:
    async with rls_connection(auth.claims) as conn:
        row = await UserProfileRepo(conn).get(auth.user_id)
    # `None` (profile not yet created) is a valid response — the frontend renders an
    # empty form, not an error.
    return UserProfileOut.model_validate(row) if row is not None else None


@router.patch("", response_model=UserProfileOut)
@router.patch("/", response_model=UserProfileOut, include_in_schema=False)
async def update_profile(
    payload: UserProfileUpdate, auth: AuthContext = Depends(get_current_user)
) -> UserProfileOut:
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise ValidationError("PATCH wymaga przynajmniej jednego pola do aktualizacji.")
    async with rls_connection(auth.claims) as conn:
        row = await UserProfileRepo(conn).upsert(auth.user_id, fields)
    return UserProfileOut.model_validate(row)
