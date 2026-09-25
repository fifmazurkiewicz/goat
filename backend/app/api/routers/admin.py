"""`/admin` router — ONLY `service_role` + explicit, code-level verification of `profiles.is_admin`.

"Hiding in UI is not authorization" — docs/technical/security.md section 2 and
docs/technical/architecture.md section 2. The `require_admin` dependency
(`app/core/security.py`) verifies `profiles.is_admin` in the `service_role` context,
independent of RLS.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.db import login_role_connection, service_role_connection
from app.core.exceptions import ForbiddenError
from app.core.security import AuthContext, require_admin
from app.core.supabase_admin import get_supabase_admin_client
from app.domain.usage.service import current_period_start
from app.models.schemas import (
    AdminUserOut,
    ApprovalUpdate,
    PasswordResetOut,
    PersonaLimitUpdate,
    UsageBudgetUpdate,
)
from app.repositories.profiles_repo import ProfileRow, ProfilesRepo
from app.repositories.usage_limits_repo import UsageLimitsRepo

router = APIRouter(prefix="/admin", tags=["admin"])


def _admin_user_out(
    profile: ProfileRow,
    *,
    email: str | None = None,
    cost_usd_used: float = 0.0,
) -> AdminUserOut:
    return AdminUserOut(
        id=profile.id,
        email=email,
        is_admin=profile.is_admin,
        is_approved=profile.is_approved,
        max_active_personas=profile.max_active_personas,
        usage_budget_usd=profile.usage_budget_usd,
        cost_usd_used=cost_usd_used,
        created_at=profile.created_at,
    )


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(auth: AuthContext = Depends(require_admin)) -> list[AdminUserOut]:
    period_start = current_period_start()
    async with service_role_connection() as conn:
        profiles = await ProfilesRepo(conn).list_all()
        usage_by_user = await UsageLimitsRepo(conn).list_for_period(period_start)

    # `auth.users` is readable as the login role, not as `service_role`.
    async with login_role_connection() as conn:
        emails = await ProfilesRepo(conn).list_emails()

    return [
        _admin_user_out(
            profile,
            email=emails.get(profile.id),
            cost_usd_used=(usage_by_user[profile.id].cost_usd_used if profile.id in usage_by_user else 0.0),
        )
        for profile in profiles
    ]


@router.patch("/users/{user_id}/persona-limit", response_model=AdminUserOut)
async def update_persona_limit(
    user_id: str,
    payload: PersonaLimitUpdate,
    auth: AuthContext = Depends(require_admin),
) -> AdminUserOut:
    """Sets `profiles.max_active_personas` per account (ADR-12) — replaces the global
    "5" constant. The DB trigger (`enforce_persona_limit`) remains the last line of
    defense regardless of this setting."""
    async with service_role_connection() as conn:
        profile = await ProfilesRepo(conn).update_max_active_personas(user_id, payload.max_active_personas)
    return _admin_user_out(profile)


@router.patch("/users/{user_id}/usage-budget", response_model=AdminUserOut)
async def update_usage_budget(
    user_id: str,
    payload: UsageBudgetUpdate,
    auth: AuthContext = Depends(require_admin),
) -> AdminUserOut:
    """Sets `profiles.usage_budget_usd` per account (ADR-16) — pattern identical to
    `update_persona_limit`."""
    async with service_role_connection() as conn:
        profile = await ProfilesRepo(conn).update_usage_budget(user_id, payload.usage_budget_usd)
    return _admin_user_out(profile)


@router.patch("/users/{user_id}/approval", response_model=AdminUserOut)
async def update_user_approval(
    user_id: str,
    payload: ApprovalUpdate,
    auth: AuthContext = Depends(require_admin),
) -> AdminUserOut:
    """Accept or revoke access (ADR-22). Does not change `usage_budget_usd`."""
    if user_id == auth.user_id and not payload.is_approved:
        raise ForbiddenError("Nie możesz cofnąć sobie dostępu.")
    async with service_role_connection() as conn:
        profile = await ProfilesRepo(conn).update_is_approved(user_id, payload.is_approved)
    return _admin_user_out(profile)


@router.post("/users/{user_id}/reset-password", response_model=PasswordResetOut)
async def reset_password(user_id: str, auth: AuthContext = Depends(require_admin)) -> PasswordResetOut:
    """Password reset via Supabase Admin API (`app/core/supabase_admin.py`) — the
    temporary password is returned ONCE in the response, for manual delivery to the user."""
    temp_password = await get_supabase_admin_client().reset_password(user_id)
    return PasswordResetOut(temporary_password=temp_password)
