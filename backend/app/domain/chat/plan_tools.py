"""Narzędzia czatu do odczytu/edycji/przebudowy planu (Faza 3).

Reużywa `PlansRepo` + `PlanOrchestrator.generate_plan` (architecture.md §4).
Błędy walidacji → dict z `error`, nigdy wyjątek do LLM loop.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.exceptions import ConflictError
from app.domain.jobs.runner import enqueue_plan_generation_async, enqueue_plan_harmonize_async
from app.models.schemas import PlanItemContent
from app.repositories.plans_repo import PlansRepo


def period_end_date(period_type: str, start_date: date) -> date:
    if period_type == "week":
        return start_date + timedelta(days=6)
    last_day = calendar.monthrange(start_date.year, start_date.month)[1]
    return start_date.replace(day=last_day)


class ChatPlanToolsService:
    def __init__(self, conn: AsyncConnection, *, claims: dict[str, Any]) -> None:
        self._repo = PlansRepo(conn)
        self._claims = claims

    async def get_plan(
        self,
        *,
        user_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        plan = await self._repo.get_latest_editable_plan_for_user(user_id)
        if plan is None:
            return {
                "status": "empty",
                "message": "Brak planu — zaproponuj rebuild_plan albo generowanie w zakładce Plany.",
            }
        items = await self._repo.list_items_for_plan(plan.id)
        filtered = []
        for item in items:
            if start_date is not None and item.item_date < start_date:
                continue
            if end_date is not None and item.item_date > end_date:
                continue
            content = item.content if isinstance(item.content, dict) else {}
            filtered.append(
                {
                    "id": item.id,
                    "item_date": item.item_date.isoformat(),
                    "item_type": item.item_type,
                    "persona_id": item.persona_id,
                    "title": content.get("title"),
                    "notes": content.get("notes"),
                    "columns": content.get("columns"),
                    "rows_count": len(content.get("rows") or []),
                }
            )
        return {
            "status": "ok",
            "plan_id": plan.id,
            "period_type": plan.period_type,
            "start_date": plan.start_date.isoformat(),
            "end_date": plan.end_date.isoformat(),
            "plan_status": plan.status,
            "items": filtered,
        }

    async def upsert_plan_items(
        self,
        *,
        user_id: str,
        persona_id: str,
        entries: list[dict[str, Any]],
        allowed_persona_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        plan = await self._repo.get_latest_editable_plan_for_user(user_id)
        if plan is None:
            generating = await self._repo.get_latest_plan_for_user(user_id)
            if generating is not None and generating.status == "generating":
                return {
                    "error": "Plan jest w trakcie generowania — poczekaj na zakończenie "
                    "lub użyj rebuild_plan po zakończeniu joba."
                }
            return {
                "error": "Brak planu do edycji. Najpierw rebuild_plan (tydzień/miesiąc) "
                "lub wygeneruj plan w zakładce Plany."
            }

        allowed = set(allowed_persona_ids or [persona_id])

        outcomes: list[dict[str, Any]] = []
        touched_dates: list[str] = []
        for index, entry in enumerate(entries):
            try:
                item_date = date.fromisoformat(str(entry["item_date"]))
            except (KeyError, ValueError) as exc:
                outcomes.append({"index": index, "status": "error", "error": f"Zła data: {exc}"})
                continue

            if item_date < plan.start_date or item_date > plan.end_date:
                outcomes.append(
                    {
                        "index": index,
                        "status": "error",
                        "error": f"Data {item_date} poza zakresem planu "
                        f"({plan.start_date}–{plan.end_date}).",
                    }
                )
                continue

            target_persona_id = str(entry.get("persona_id") or persona_id)
            if target_persona_id not in allowed:
                outcomes.append(
                    {
                        "index": index,
                        "status": "error",
                        "error": "Nie można zapisać pozycji dla tej persony.",
                    }
                )
                continue

            try:
                content = PlanItemContent.model_validate(
                    {
                        "title": entry.get("title"),
                        "columns": entry.get("columns"),
                        "rows": entry.get("rows"),
                        "notes": entry.get("notes"),
                    }
                ).model_dump()
            except Exception as exc:  # noqa: BLE001 — wraca do modelu
                outcomes.append({"index": index, "status": "error", "error": str(exc)})
                continue

            item_id = entry.get("item_id")
            if item_id:
                existing = await self._repo.get_item(str(item_id))
                if existing is None or existing.plan_id != plan.id:
                    outcomes.append(
                        {"index": index, "status": "error", "error": "Nie znaleziono pozycji planu."}
                    )
                    continue
                if existing.persona_id != target_persona_id:
                    outcomes.append(
                        {
                            "index": index,
                            "status": "error",
                            "error": "Nie można przenieść pozycji na inną personę.",
                        }
                    )
                    continue
                await self._repo.update_item_content(existing.id, content)
                outcomes.append({"index": index, "status": "ok", "item_id": existing.id})
                touched_dates.append(item_date.isoformat())
            else:
                inserted = await self._repo.insert_items(
                    plan.id,
                    [
                        {
                            "item_date": item_date,
                            "item_type": str(entry.get("item_type") or "training"),
                            "persona_id": target_persona_id,
                            "content": content,
                        }
                    ],
                )
                outcomes.append(
                    {"index": index, "status": "ok", "item_id": inserted[0].id if inserted else None}
                )
                touched_dates.append(item_date.isoformat())

        ok = sum(1 for o in outcomes if o["status"] == "ok")
        harmonize_job: str | None = None
        if ok > 0 and touched_dates:
            unique_dates = sorted(set(touched_dates))
            harmonize_job = await enqueue_plan_harmonize_async(
                plan_id=plan.id,
                user_id=user_id,
                claims=self._claims,
                dates=unique_dates,
            )
        else:
            harmonize_job = None

        result = {
            "status": "ok" if ok == len(outcomes) else ("partial" if ok else "error"),
            "upserted": ok,
            "results": outcomes,
        }
        if harmonize_job:
            result["harmonize_job_id"] = harmonize_job
        return result

    async def rebuild_plan(
        self,
        *,
        user_id: str,
        period_type: str,
        start_date: date,
    ) -> dict[str, Any]:
        if period_type not in ("week", "month"):
            return {"error": "period_type musi być 'week' albo 'month'."}
        end = period_end_date(period_type, start_date)
        try:
            plan = await self._repo.create_plan(
                user_id=user_id,
                period_type=period_type,
                start_date=start_date,
                end_date=end,
            )
            job = await self._repo.create_job(plan_id=plan.id, user_id=user_id)
        except ConflictError as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Nie udało się utworzyć joba planu: {exc}"}

        bg_job_id = await enqueue_plan_generation_async(
            plan_id=plan.id,
            plan_job_id=job.id,
            user_id=user_id,
            claims=self._claims,
            background_tasks=None,
        )
        return {
            "status": "ok",
            "job_id": job.id,
            "plan_id": plan.id,
            "background_job_id": bg_job_id,
            "message": "Generowanie planu uruchomione — wynik w zakładce Plany.",
        }
