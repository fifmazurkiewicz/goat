"""Router `/usage` — bieżące zużycie budżetu USD (ADR-16) dla badge'a FE."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends

from app.core.db import rls_connection
from app.core.security import AuthContext, get_current_user
from app.domain.usage.service import current_period_start
from app.models.schemas import UsageLimitsOut
from app.repositories.profiles_repo import DEFAULT_USAGE_BUDGET_USD, ProfilesRepo
from app.repositories.usage_limits_repo import UsageLimitsRepo

router = APIRouter(prefix="/usage", tags=["usage"])


def _period_renews_at(period_start: date) -> date:
    if period_start.month == 12:
        return date(period_start.year + 1, 1, 1)
    return date(period_start.year, period_start.month + 1, 1)


@router.get("", response_model=UsageLimitsOut)
@router.get("/", response_model=UsageLimitsOut, include_in_schema=False)
async def get_usage(auth: AuthContext = Depends(get_current_user)) -> UsageLimitsOut:
    period_start = current_period_start()
    async with rls_connection(auth.claims) as conn:
        profile = await ProfilesRepo(conn).get(auth.user_id)
        usage = await UsageLimitsRepo(conn).get(auth.user_id, period_start)

    budget = (
        float(profile.usage_budget_usd)
        if profile is not None
        else float(DEFAULT_USAGE_BUDGET_USD)
    )
    return UsageLimitsOut(
        user_id=auth.user_id,
        period_start=period_start,
        period_renews_at=_period_renews_at(period_start),
        messages_used=int(getattr(usage, "messages_used", 0) or 0),
        tokens_used=int(getattr(usage, "tokens_used", 0) or 0),
        plan_generations_used=int(getattr(usage, "plan_generations_used", 0) or 0),
        cost_usd_used=float(getattr(usage, "cost_usd_used", 0.0) or 0.0),
        usage_budget_usd=budget,
    )
