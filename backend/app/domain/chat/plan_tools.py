"""Chat tools for reading/editing/rebuilding the plan (Phase 3).

Reuses `PlansRepo` + `PlanOrchestrator.generate_plan` (architecture.md §4).
Validation errors -> dict with `error`, never an exception to the LLM loop.
"""

from __future__ import annotations

import calendar
import json
from datetime import date, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.exceptions import ConflictError
from app.domain.chat.team_lead import user_confirms_rebuild
from app.domain.jobs.runner import enqueue_plan_generation_async, enqueue_plan_harmonize_async
from app.models.schemas import PlanItemContent
from app.repositories.plans_repo import PlansRepo


def tool_json_shows_rebuild_pending(contents: list[str]) -> bool:
    """True if history has `needs_confirm` after the last successful rebuild enqueue."""
    pending = False
    for raw in contents:
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        if parsed.get("status") == "needs_confirm":
            pending = True
        elif parsed.get("status") == "ok" and parsed.get("job_id"):
            pending = False
    return pending


def decide_rebuild_plan_action(
    *,
    user_message: str,
    active_job_id: str | None,
    confirmed: bool = False,
    rebuild_pending: bool = False,
) -> dict[str, Any]:
    """Idempotent reuse / explicit confirm / enqueue — never a silent second 3-stage job.

    `confirmed` from the model is ignored. Enqueue only after a prior `needs_confirm`
    plus the user's next-turn „tak”.
    """
    del confirmed  # never trust tool JSON
    if active_job_id:
        return {
            "action": "reuse",
            "job_id": active_job_id,
            "message": "Przebudowa planu już trwa — czekam na ten sam job.",
        }
    if rebuild_pending and user_confirms_rebuild(user_message):
        return {"action": "enqueue"}
    return {
        "action": "needs_confirm",
        "message": "Potwierdź przebudowę planu — napisz „tak” w następnej wiadomości.",
    }


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
        user_brief: str | None = None,
        confirmed: bool = False,
        user_message: str = "",
        session_id: str | None = None,
        prior_tool_contents: list[str] | None = None,
    ) -> dict[str, Any]:
        if period_type not in ("week", "month"):
            return {"error": "period_type musi być 'week' albo 'month'."}

        history_contents: list[str] = []
        if session_id:
            from app.repositories.chat_repo import ChatRepo

            messages = await ChatRepo(self._conn).list_recent_messages_for_context(
                session_id=session_id,
                persona_id=None,
                session_type="general",
                limit=40,
            )
            history_contents = [m.content or "" for m in messages if m.role == "tool"]
        rebuild_pending = tool_json_shows_rebuild_pending(
            history_contents + list(prior_tool_contents or [])
        )

        active = await self._repo.get_active_job_for_user(user_id)
        decision = decide_rebuild_plan_action(
            confirmed=confirmed,
            user_message=user_message,
            active_job_id=active.id if active else None,
            rebuild_pending=rebuild_pending,
        )
        if decision["action"] == "needs_confirm":
            return {"status": "needs_confirm", "message": decision["message"]}
        if decision["action"] == "reuse" and active is not None:
            return {
                "status": "ok",
                "job_id": active.id,
                "plan_id": active.plan_id,
                "idempotent": True,
                "message": decision["message"],
            }

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
            existing = await self._repo.get_active_job_for_user(user_id)
            if existing is not None:
                return {
                    "status": "ok",
                    "job_id": existing.id,
                    "plan_id": existing.plan_id,
                    "idempotent": True,
                    "message": "Przebudowa planu już trwa — czekam na ten sam job.",
                }
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Nie udało się utworzyć joba planu: {exc}"}

        bg_job_id = await enqueue_plan_generation_async(
            plan_id=plan.id,
            plan_job_id=job.id,
            user_id=user_id,
            claims=self._claims,
            background_tasks=None,
            user_brief=user_brief,
        )
        return {
            "status": "ok",
            "job_id": job.id,
            "plan_id": plan.id,
            "background_job_id": bg_job_id,
            "message": "Generowanie planu uruchomione — wynik w zakładce Plany.",
        }
