"""`/admin` router — ONLY `service_role` + explicit, code-level verification of `profiles.is_admin`.

"Hiding in UI is not authorization" — docs/technical/security.md section 2 and
docs/technical/architecture.md section 2. The `require_admin` dependency
(`app/core/security.py`) verifies `profiles.is_admin` in the `service_role` context,
independent of RLS.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.db import service_role_connection
from app.core.security import AuthContext, require_admin
from app.core.supabase_admin import get_supabase_admin_client
from app.core.version import get_deploy_info
from app.domain.usage.service import current_period_start
from app.models.schemas import (
    AdminUserOut,
    AuditLogEntryOut,
    DeployInfoOut,
    PasswordResetOut,
    PersonaLimitUpdate,
    UsageBudgetUpdate,
)
from app.repositories.admin_audit_repo import AdminAuditRepo
from app.repositories.profiles_repo import ProfilesRepo
from app.repositories.usage_limits_repo import UsageLimitsRepo

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/deploy-info", response_model=DeployInfoOut)
async def get_deploy_info_endpoint(_auth: AuthContext = Depends(require_admin)) -> DeployInfoOut:
    info = get_deploy_info(environment=settings.environment)
    return DeployInfoOut(
        app_version=info.app_version,
        environment=info.environment,
        git_sha=info.git_sha,
        git_sha_full=info.git_sha_full,
        git_branch=info.git_branch,
        build_time=info.build_time,
        git_repo=info.git_repo,
    )


@router.get("/audit-log", response_model=list[AuditLogEntryOut])
async def list_audit_log(auth: AuthContext = Depends(require_admin)) -> list[AuditLogEntryOut]:
    async with service_role_connection() as conn:
        rows = await AdminAuditRepo(conn).list_all()
    return [AuditLogEntryOut.model_validate(row) for row in rows]


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(auth: AuthContext = Depends(require_admin)) -> list[AdminUserOut]:
    period_start = current_period_start()
    async with service_role_connection() as conn:
        profiles = await ProfilesRepo(conn).list_all()
        usage_by_user = await UsageLimitsRepo(conn).list_for_period(period_start)

    emails = await get_supabase_admin_client().list_user_emails()

    return [
        AdminUserOut(
            id=profile.id,
            email=emails.get(profile.id),
            is_admin=profile.is_admin,
            max_active_personas=profile.max_active_personas,
            usage_budget_usd=profile.usage_budget_usd,
            cost_usd_used=usage_by_user[profile.id].cost_usd_used if profile.id in usage_by_user else 0.0,
            created_at=profile.created_at,
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
        profile = await ProfilesRepo(conn).update_max_active_personas(
            user_id, payload.max_active_personas
        )
        await AdminAuditRepo(conn).log(
            admin_user_id=auth.user_id,
            action="edit_persona_limit",
            target_user_id=user_id,
            details={"max_active_personas": payload.max_active_personas},
        )
    return AdminUserOut(
        id=profile.id,
        email=None,
        is_admin=profile.is_admin,
        max_active_personas=profile.max_active_personas,
        usage_budget_usd=profile.usage_budget_usd,
        created_at=profile.created_at,
    )


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
        await AdminAuditRepo(conn).log(
            admin_user_id=auth.user_id,
            action="edit_usage_budget",
            target_user_id=user_id,
            details={"usage_budget_usd": payload.usage_budget_usd},
        )
    return AdminUserOut(
        id=profile.id,
        email=None,
        is_admin=profile.is_admin,
        max_active_personas=profile.max_active_personas,
        usage_budget_usd=profile.usage_budget_usd,
        created_at=profile.created_at,
    )


@router.post("/users/{user_id}/reset-password", response_model=PasswordResetOut)
async def reset_password(user_id: str, auth: AuthContext = Depends(require_admin)) -> PasswordResetOut:
    """Password reset via Supabase Admin API (`app/core/supabase_admin.py`) — the
    temporary password is returned ONCE in the response, for manual delivery to the user."""
    temp_password = await get_supabase_admin_client().reset_password(user_id)
    async with service_role_connection() as conn:
        await AdminAuditRepo(conn).log(
            admin_user_id=auth.user_id, action="reset_password", target_user_id=user_id
        )
    return PasswordResetOut(temporary_password=temp_password)
