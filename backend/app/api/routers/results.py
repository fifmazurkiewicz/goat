"""`/results` router — results logged by the agent (tool calling) or manually.

See docs/technical/database-schema.md (the `results` table) and docs/adr/decisions.md
ADR-9 (trend charts per metric in `/results`, no schema changes beyond the
`results_user_category_metric_date` index).
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.core.db import rls_connection
from app.core.security import AuthContext, get_current_user, require_approved
from app.domain.results.metrics_cache import allowed_metrics_cache
from app.domain.results.service import ResultsService
from app.models.schemas import ResultCategory, ResultCreate, ResultOut, ResultUpdate
from app.repositories.results_repo import ResultsRepo

router = APIRouter(
    prefix="/results",
    tags=["results"],
    dependencies=[Depends(require_approved)],
)


@router.get("", response_model=list[ResultOut])
@router.get("/", response_model=list[ResultOut], include_in_schema=False)
async def list_results(
    category: ResultCategory | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    auth: AuthContext = Depends(get_current_user),
) -> list[ResultOut]:
    async with rls_connection(auth.claims) as conn:
        service = ResultsService(ResultsRepo(conn), allowed_metrics_cache)
        rows = await service.list_results(category=category, date_from=date_from, date_to=date_to)
    return [ResultOut.model_validate(row) for row in rows]


@router.post("", response_model=ResultOut, status_code=201)
@router.post("/", response_model=ResultOut, status_code=201, include_in_schema=False)
async def create_result(
    payload: ResultCreate, auth: AuthContext = Depends(get_current_user)
) -> ResultOut:
    async with rls_connection(auth.claims) as conn:
        service = ResultsService(ResultsRepo(conn), allowed_metrics_cache)
        row = await service.create_manual(auth.user_id, payload.model_dump())
    return ResultOut.model_validate(row)


@router.patch("/{result_id}", response_model=ResultOut)
async def update_result(
    result_id: str, payload: ResultUpdate, auth: AuthContext = Depends(get_current_user)
) -> ResultOut:
    async with rls_connection(auth.claims) as conn:
        service = ResultsService(ResultsRepo(conn), allowed_metrics_cache)
        row = await service.update_manual(
            result_id, auth.user_id, payload.model_dump(exclude_unset=True)
        )
    return ResultOut.model_validate(row)


@router.delete("/{result_id}", status_code=204)
async def delete_result(result_id: str, auth: AuthContext = Depends(get_current_user)) -> None:
    async with rls_connection(auth.claims) as conn:
        service = ResultsService(ResultsRepo(conn), allowed_metrics_cache)
        await service.delete_manual(result_id, auth.user_id)
