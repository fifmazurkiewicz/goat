"""User privacy controls: consent, portable export and account erasure."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import settings
from app.core.db import login_role_connection, rls_connection, service_role_connection
from app.core.exceptions import ValidationError
from app.core.security import AuthContext, get_current_user, require_admin
from app.core.supabase_admin import SupabaseAdminClient, get_supabase_admin_client
from app.repositories.privacy_repo import (
    AI_DISCLOSURE_NOTICE,
    AI_DISCLOSURE_VERSION,
    HEALTH_CONSENT_NOTICE,
    HEALTH_CONSENT_VERSION,
    PrivacyRepo,
)

router = APIRouter(prefix="/privacy", tags=["privacy"])


class ConsentGrantRequest(BaseModel):
    accept_health_data: bool
    acknowledge_ai_disclosure: bool = False


def _status(active: dict[str, dict[str, object]]) -> dict[str, object]:
    return {
        "health_data": {
            "active": active.get("health_data", {}).get("version") == HEALTH_CONSENT_VERSION,
            "required_version": HEALTH_CONSENT_VERSION,
            **(active.get("health_data") or {}),
        },
        "ai_disclosure": {
            "acknowledged": active.get("ai_disclosure", {}).get("version") == AI_DISCLOSURE_VERSION,
            "required_version": AI_DISCLOSURE_VERSION,
            **(active.get("ai_disclosure") or {}),
        },
    }


@router.get("/consent")
async def get_consent(auth: AuthContext = Depends(get_current_user)) -> dict[str, object]:
    async with rls_connection(auth.claims) as conn:
        active = await PrivacyRepo(conn).active_consents(auth.user_id)
    return _status(active)


@router.post("/consent/grant")
async def grant_consent(
    payload: ConsentGrantRequest, auth: AuthContext = Depends(get_current_user)
) -> dict[str, object]:
    if not payload.accept_health_data:
        raise ValidationError("Zgoda na dane zdrowotne musi być udzielona świadomie.")
    if not payload.acknowledge_ai_disclosure:
        raise ValidationError("Przed użyciem funkcji AI potwierdź zapoznanie się z informacją o AI.")
    async with rls_connection(auth.claims) as conn:
        repo = PrivacyRepo(conn)
        await repo.grant(auth.user_id, "health_data", HEALTH_CONSENT_VERSION, HEALTH_CONSENT_NOTICE)
        if payload.acknowledge_ai_disclosure:
            await repo.grant(auth.user_id, "ai_disclosure", AI_DISCLOSURE_VERSION, AI_DISCLOSURE_NOTICE)
        active = await repo.active_consents(auth.user_id)
    return _status(active)


@router.post("/consent/withdraw")
async def withdraw_consent(auth: AuthContext = Depends(get_current_user)) -> dict[str, object]:
    async with rls_connection(auth.claims) as conn:
        repo = PrivacyRepo(conn)
        withdrawn_at = await repo.withdraw_health(auth.user_id)
        active = await repo.active_consents(auth.user_id)
    return {**_status(active), "withdrawn_at": withdrawn_at}


@router.get("/export")
async def export_account(auth: AuthContext = Depends(get_current_user)) -> JSONResponse:
    async with rls_connection(auth.claims) as conn:
        data = await PrivacyRepo(conn).export_user(auth.user_id)
    payload = {"exported_at": datetime.now(UTC), "format_version": 1, "data": data}
    return JSONResponse(
        content=jsonable_encoder(payload),
        headers={"Content-Disposition": 'attachment; filename="goat-data-export.json"'},
    )


@router.delete("/account", status_code=204)
async def delete_account(
    auth: AuthContext = Depends(get_current_user),
    admin_client: SupabaseAdminClient = Depends(get_supabase_admin_client),
) -> Response:
    if settings.dev_auth_enabled:
        async with login_role_connection() as conn:
            await conn.execute(text("DELETE FROM auth.users WHERE id = :user_id"), {"user_id": auth.user_id})
    else:
        await admin_client.delete_user(auth.user_id)
    return Response(status_code=204)


@router.post("/retention/run", dependencies=[Depends(require_admin)])
async def run_retention() -> dict[str, object]:
    """Operator-triggered cleanup; intended for a trusted scheduler."""
    async with service_role_connection() as conn:
        deleted = await PrivacyRepo(conn).purge_expired(
            chat_days=settings.privacy_chat_retention_days,
            job_days=settings.privacy_completed_job_retention_days,
            moderation_days=settings.privacy_moderation_snippet_retention_days,
        )
    return {"deleted": deleted}
