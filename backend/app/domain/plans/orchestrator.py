"""`PlanOrchestrator` — 3-stage plan generation pipeline (architecture.md §4, ADR-2).

Runs from FastAPI `BackgroundTasks` (no separate Render Worker — ADR-1), in the same
process as the web app. Product priority: plan SYNCHRONIZATION across active personas,
not just quality of a single persona in isolation.

**Architectural exception (like `ChatOrchestrator`):** this module KNOWS concrete repos and
`app.core.db.rls_connection` instead of pure `Protocol` — architecture.md §4 requires
explicitly that "each coroutine takes its OWN DB connection from the pool", which conflicts
with the typical "one connection per request-scoped service" pattern used in other domain
services. Unit tests (`tests/test_plan_orchestrator*.py`) therefore cover mainly pure
helper functions (parse/patch), not the full orchestrator end-to-end (would require a real
DB — outside unit-test scope).

**LLM JSON schema `rows` format: LIST OF string LISTS (positional, per `resolve_persona_columns`
order), NOT a list of objects/dicts.** OpenRouter/OpenAI `response_format: json_schema` in
`strict:true` mode requires explicitly defined object keys — per-persona columns are dynamic
(`template_overrides`), so `properties` for arbitrary column names cannot be declared upfront.
A list of string lists is schema-safe and the backend zips it back with columns when building
`PlanItemContent`.
"""

from __future__ import annotations

import asyncio
import time
from datetime import date, timedelta
from typing import Any, Protocol

import structlog

from app.core.config import settings
from app.core.db import rls_connection, service_role_connection
from app.core.dependencies import get_pricing_cache
from app.domain.chat.preamble import build_system_prompt
from app.domain.chat.team_lead import plan_brief_excludes_persona_type
from app.domain.personas.service import resolve_persona_columns
from app.domain.usage.service import UsageLimitService
from app.observability.langfuse import observe
from app.observability.langfuse import update as update_observation
from app.repositories.personas_repo import PersonasRepo
from app.repositories.plans_repo import PlanItemRow, PlansRepo
from app.repositories.profiles_repo import ProfilesRepo
from app.repositories.results_repo import ResultsRepo
from app.repositories.templates_repo import PersonaTemplatesRepo, PlanTemplatesRepo
from app.repositories.usage_limits_repo import UsageLimitsRepo
from app.repositories.user_profile_repo import UserProfileRepo

logger = structlog.get_logger(__name__)


def should_finalize_plan_job_success(status: str | None) -> bool:
    """Only an still-active job may be written as success after `_run`."""
    return status in ("pending", "running")


def _format_user_brief_block(user_brief: str | None) -> str:
    text = (user_brief or "").strip()
    if not text:
        return ""
    return (
        "\n[BRIEF UŻYTKOWNIKA — TWARDE OGRANICZENIA]\n"
        f"{text}\n"
        "Przestrzegaj bezwzględnie. Jeśli brief wyklucza dyscyplinę (np. badminton), "
        "NIE planuj jej — zamiast tego regeneracja / siła / bieg zgodnie z briefem.\n"
    )


class PlannerLLMClientProtocol(Protocol):
    async def complete_json(
        self, *, model: str, messages: list[dict], json_schema: dict, max_tokens: int = 300
    ) -> dict: ...


_COORDINATOR_SCHEMA = {
    "name": "plan_skeleton",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "days": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string"},
                        "focus": {"type": "string"},
                        "intensity": {
                            "type": "string",
                            "enum": ["rest", "light", "moderate", "intense"],
                        },
                    },
                    "required": ["date", "focus", "intensity"],
                    "additionalProperties": False,
                },
            },
            "notes": {"type": "string"},
        },
        "required": ["days", "notes"],
        "additionalProperties": False,
    },
}


def _persona_items_schema() -> dict:
    return {
        "name": "persona_plan_items",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_date": {"type": "string"},
                            "title": {"type": "string"},
                            "rows": {
                                "type": "array",
                                "items": {"type": "array", "items": {"type": "string"}},
                            },
                            "notes": {"type": "string"},
                        },
                        "required": ["item_date", "title", "rows", "notes"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["items"],
            "additionalProperties": False,
        },
    }


def _harmonization_schema(persona_ids: list[str]) -> dict:
    return {
        "name": "plan_harmonization_patches",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "patches": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "persona_id": {"type": "string", "enum": persona_ids},
                            "item_date": {"type": "string"},
                            "action": {
                                "type": "string",
                                "enum": ["update", "delete"],
                                "description": "update = zmień treść; delete = usuń pozycję",
                            },
                            "title": {"type": "string"},
                            "rows": {
                                "type": "array",
                                "items": {"type": "array", "items": {"type": "string"}},
                            },
                            "notes": {"type": "string"},
                        },
                        "required": [
                            "persona_id",
                            "item_date",
                            "action",
                            "title",
                            "rows",
                            "notes",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["patches"],
            "additionalProperties": False,
        },
    }


def iter_dates(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def rows_to_content(*, title: str, columns: list[str], rows: list[list[str]], notes: str | None) -> dict[str, Any]:
    """`PlanItemContent` — zips positional `rows` (from LLM) with `columns` (`resolve_persona_columns`)."""
    dict_rows = [dict(zip(columns, row, strict=False)) for row in rows]
    return {"title": title, "columns": columns, "rows": dict_rows, "notes": notes}


class PlanOrchestrator:
    def __init__(
        self,
        llm_client: PlannerLLMClientProtocol,
        *,
        planner_model: str | None = None,
        chat_model: str | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._planner_model = planner_model or settings.openrouter_plan_model
        self._chat_model = chat_model or settings.openrouter_chat_model

    @staticmethod
    def _persona_output_budget(period_type: str) -> int:
        return (
            settings.plan_month_persona_max_output_tokens
            if period_type == "month"
            else settings.plan_week_persona_max_output_tokens
        )

    @staticmethod
    def _coordinator_output_budget(period_type: str) -> int:
        return (
            settings.plan_month_coordinator_max_output_tokens
            if period_type == "month"
            else settings.plan_week_coordinator_max_output_tokens
        )

    async def generate_plan(
        self,
        *,
        plan_id: str,
        job_id: str,
        user_id: str,
        claims: dict,
        user_brief: str | None = None,
        persona_ids: list[str] | None = None,
    ) -> None:
        structlog.contextvars.bind_contextvars(job_id=job_id, plan_id=plan_id)
        with observe(
            name="plan_generation",
            as_type="chain",
            input={"user_brief": user_brief},
            metadata={"job_id": job_id, "plan_id": plan_id, "user_id": user_id},
        ) as observation:
            try:
                await self._run(
                    plan_id=plan_id,
                    job_id=job_id,
                    user_id=user_id,
                    claims=claims,
                    user_brief=user_brief,
                )
                update_observation(observation, output={"status": "success"})
            except asyncio.CancelledError:
                update_observation(observation, output={"status": "cancelled"})
                await self._persist_cancelled(job_id=job_id, plan_id=plan_id, claims=claims)
                raise
            except Exception as exc:  # noqa: BLE001 — top-level safety net dla background taska
                update_observation(
                    observation, output={"status": "error"}, level="ERROR", status_message=str(exc)[:500]
                )
                logger.error("plan_generation_unexpected_error", error=str(exc), exc_info=exc)
                try:
                    async with rls_connection(claims) as conn:
                        repo = PlansRepo(conn)
                        marked = await repo.update_job_status(job_id, "error", error_message=str(exc)[:500])
                        if marked:
                            await repo.update_plan_status(plan_id, "error")
                except Exception:  # noqa: BLE001 — nie eskalujemy błędu przy zapisie błędu
                    logger.error("plan_generation_failed_to_persist_error_state")

    async def _persist_cancelled(self, *, job_id: str, plan_id: str, claims: dict) -> None:
        try:
            async with rls_connection(claims) as conn:
                repo = PlansRepo(conn)
                marked = await repo.update_job_status(job_id, "error", error_message="Anulowano przez użytkownika.")
                if marked:
                    await repo.update_plan_status(plan_id, "error")
        except Exception:  # noqa: BLE001
            logger.error("plan_generation_failed_to_persist_cancel_state")

    async def _abort_if_cancelled(self, *, job_id: str, claims: dict) -> None:
        async with rls_connection(claims) as conn:
            job = await PlansRepo(conn).get_job(job_id)
            if job is None or not should_finalize_plan_job_success(job.status):
                raise asyncio.CancelledError

    async def _run(
        self,
        *,
        plan_id: str,
        job_id: str,
        user_id: str,
        claims: dict,
        user_brief: str | None = None,
    ) -> None:
        async with rls_connection(claims) as conn:
            plans_repo = PlansRepo(conn)
            claimed = await plans_repo.update_job_status(job_id, "running")
            if not claimed:
                raise asyncio.CancelledError
            await plans_repo.increment_attempts(job_id)

            plan = await plans_repo.get_plan(plan_id)
            if plan is None:
                marked = await plans_repo.update_job_status(job_id, "error", error_message="Plan nie istnieje.")
                if marked:
                    await plans_repo.update_plan_status(plan_id, "error")
                return

            active_personas = await PersonasRepo(conn).list_active_for_user(user_id)
            if persona_ids is not None:
                active_personas = [p for p in active_personas if p.id in set(persona_ids)]
            if user_brief:
                active_personas = [
                    p for p in active_personas if not plan_brief_excludes_persona_type(user_brief, p.type)
                ]
            recent_results = await ResultsRepo(conn).list_recent_for_planner(category=None, limit=50)
            user_profile_row = await UserProfileRepo(conn).get(user_id)

            plan_templates_repo = PlanTemplatesRepo(conn)
            persona_columns: dict[str, list[str]] = {}
            for persona in active_personas:
                template = await plan_templates_repo.get(persona.plan_template_id) if persona.plan_template_id else None
                persona_columns[persona.id] = resolve_persona_columns(
                    {"template_overrides": persona.template_overrides},
                    {"default_columns": template.default_columns} if template else None,
                )

            await plans_repo.ensure_job_personas(job_id, [p.id for p in active_personas])
            job_personas = await plans_repo.list_job_personas(job_id)
            done_persona_ids = {jp.persona_id for jp in job_personas if jp.status == "done"}

        if not active_personas:
            async with rls_connection(claims) as conn:
                repo = PlansRepo(conn)
                marked = await repo.update_job_status(job_id, "error", error_message="Brak aktywnych person.")
                if marked:
                    await repo.update_plan_status(plan_id, "error")
            return

        personas_to_generate = [p for p in active_personas if p.id not in done_persona_ids]

        reserved_period, estimated_total_cost = await self._reserve_budget(
            claims=claims, user_id=user_id, persona_count=max(len(personas_to_generate), 1)
        )
        logger.info(
            "plan_generation_budget_reserved",
            estimated_usd=estimated_total_cost,
            user_brief_set=bool(user_brief),
        )
        await self._abort_if_cancelled(job_id=job_id, claims=claims)

        user_profile_summary = _summarize_user_profile(user_profile_row)
        results_summary = _summarize_results(recent_results)

        skeleton: dict[str, Any]
        if done_persona_ids:
            skeleton = {"days": [], "notes": "Wznowiono job — pominięto koordynator (persony done już zapisane)."}
        else:
            skeleton = await self._run_coordinator_pass(
                plan=plan,
                active_personas=active_personas,
                results_summary=results_summary,
                user_brief=user_brief,
            )

        semaphore = asyncio.Semaphore(settings.plan_persona_concurrency_limit)
        generate_tasks = [
            self._generate_and_persist_persona(
                persona=persona,
                columns=persona_columns[persona.id],
                skeleton=skeleton,
                results_summary=results_summary,
                user_profile_summary=user_profile_summary,
                plan=plan,
                plan_id=plan_id,
                job_id=job_id,
                claims=claims,
                semaphore=semaphore,
                user_brief=user_brief,
            )
            for persona in personas_to_generate
        ]
        if generate_tasks:
            await asyncio.gather(*generate_tasks, return_exceptions=True)
        await self._abort_if_cancelled(job_id=job_id, claims=claims)

        async with rls_connection(claims) as conn:
            plans_repo = PlansRepo(conn)
            job_personas_after = await plans_repo.list_job_personas(job_id)
            succeeded_personas = [
                p
                for p in active_personas
                if any(jp.persona_id == p.id and jp.status == "done" for jp in job_personas_after)
            ]

        if not succeeded_personas:
            async with rls_connection(claims) as conn:
                repo = PlansRepo(conn)
                marked = await repo.update_job_status(
                    job_id,
                    "error",
                    error_message="Wszystkie persony zawiodły przy generowaniu planu.",
                )
                if marked:
                    await repo.update_plan_status(plan_id, "error")
            await self._reconcile_plan_budget(
                claims=claims,
                user_id=user_id,
                period_start=reserved_period,
                reserved_usd=estimated_total_cost,
            )
            return

        async with rls_connection(claims) as conn:
            plans_repo = PlansRepo(conn)
            all_items = await plans_repo.list_items_for_plan(plan_id)
            item_lookup = {(item.persona_id, item.item_date.isoformat()): item for item in all_items}

        try:
            await self._run_harmonization(
                succeeded_personas=succeeded_personas,
                item_lookup=item_lookup,
                plan=plan,
                claims=claims,
                user_brief=user_brief,
            )
        except Exception as exc:  # noqa: BLE001 — harmonizacja nie blokuje draftu
            logger.warning("plan_harmonization_failed", error=str(exc))

        all_succeeded = len(succeeded_personas) == len(active_personas)
        async with rls_connection(claims) as conn:
            repo = PlansRepo(conn)
            finalized = await repo.update_job_status(job_id, "success" if all_succeeded else "partial_success")
            if not finalized:
                return
            await repo.update_plan_status(plan_id, "ready" if all_succeeded else "partial_ready")

        await self._reconcile_plan_budget(
            claims=claims,
            user_id=user_id,
            period_start=reserved_period,
            reserved_usd=estimated_total_cost,
        )

    async def _reserve_budget(self, *, claims: dict, user_id: str, persona_count: int) -> tuple[Any, float]:
        async with rls_connection(claims) as conn:
            usage_service = UsageLimitService(UsageLimitsRepo(conn), ProfilesRepo(conn), get_pricing_cache())
            # Rough estimate: coordinator (cheap) + N personas + harmonization (PLANNER_MODEL).
            estimated = await usage_service.estimate_turn_cost_usd(
                model=self._planner_model,
                prompt_text_length_chars=3000,
                max_output_tokens=(
                    settings.plan_month_persona_max_output_tokens * persona_count
                    + settings.plan_harmonization_max_output_tokens
                    + settings.plan_month_coordinator_max_output_tokens
                ),
            )
            period_start = await usage_service.reserve_plan_generation(user_id=user_id, estimated_cost_usd=estimated)
            return period_start, estimated

    async def _reconcile_plan_budget(
        self,
        *,
        claims: dict,
        user_id: str,
        period_start: Any,
        reserved_usd: float,
    ) -> None:
        """Correct the reserved estimate after the job — pass reserved USD, do not recompute."""
        try:
            async with rls_connection(claims) as conn:
                usage_service = UsageLimitService(UsageLimitsRepo(conn), ProfilesRepo(conn), get_pricing_cache())
                await usage_service.reconcile_actual_cost(
                    user_id=user_id,
                    period_start=period_start,
                    estimated_cost_usd=reserved_usd,
                    actual_cost_usd=reserved_usd,
                )
        except Exception as exc:  # noqa: BLE001 — usage fix must not fail the job
            logger.warning("plan_generation_usage_reconcile_failed", error=str(exc))

    async def _run_coordinator_pass(
        self,
        *,
        plan: Any,
        active_personas: list[Any],
        results_summary: str,
        user_brief: str | None = None,
    ) -> dict[str, Any]:
        roles = "\n".join(f"- {p.type}: {p.name}" for p in active_personas)
        system_message = (
            "Jesteś koordynatorem planu treningowo-dietetycznego. Na podstawie aktywnych "
            f"ról ({roles}) i ostatnich wyników użytkownika zbuduj wspólny szkielet "
            f"okresu {plan.start_date.isoformat()}..{plan.end_date.isoformat()}: dla "
            "KAŻDEGO dnia w zakresie określ 'focus' (krótki opis, np. 'trening nóg', "
            "'dzień odpoczynku', 'wysokowęglowodanowy') i 'intensity'. To wspólny "
            "kontekst dla wszystkich person — priorytet to SYNCHRONIZACJA (regeneracja "
            "uwzględniona, brak konfliktów obciążenia)."
            f"{_format_user_brief_block(user_brief)}"
        )
        user_message = f"Ostatnie wyniki użytkownika:\n{results_summary}"
        started_at = time.perf_counter()
        try:
            result = await self._llm_client.complete_json(
                model=self._chat_model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                ],
                json_schema=_COORDINATOR_SCHEMA,
                max_tokens=self._coordinator_output_budget(plan.period_type),
            )
            logger.info(
                "plan_stage_completed",
                stage="coordinator",
                duration_ms=round((time.perf_counter() - started_at) * 1000),
            )
            return result
        except Exception as exc:  # noqa: BLE001 — fallback: szkielet pusty, per-persona i tak generują
            logger.warning(
                "plan_coordinator_pass_failed",
                error=str(exc),
                duration_ms=round((time.perf_counter() - started_at) * 1000),
            )
            return {"days": [], "notes": ""}

    async def _generate_and_persist_persona(
        self,
        *,
        persona: Any,
        columns: list[str],
        skeleton: dict[str, Any],
        results_summary: str,
        user_profile_summary: str,
        plan: Any,
        plan_id: str,
        job_id: str,
        claims: dict,
        semaphore: asyncio.Semaphore,
        user_brief: str | None = None,
    ) -> None:
        async with semaphore:
            async with rls_connection(claims) as conn:
                plans_repo = PlansRepo(conn)
                await plans_repo.update_job_persona_status(job_id, persona.id, "running")
                await plans_repo.delete_items_for_persona(plan_id, persona.id)
            started_at = time.perf_counter()
            try:
                items = await self._generate_for_persona(
                    persona=persona,
                    columns=columns,
                    skeleton=skeleton,
                    results_summary=results_summary,
                    user_profile_summary=user_profile_summary,
                    plan=plan,
                    semaphore=None,
                    user_brief=user_brief,
                )
                async with rls_connection(claims) as conn:
                    plans_repo = PlansRepo(conn)
                    await plans_repo.insert_items_batch(plan_id, items)
                    await plans_repo.update_job_persona_status(job_id, persona.id, "done")
                    await plans_repo.update_plan_status(plan_id, "generating")
                logger.info(
                    "plan_stage_completed",
                    stage="persona",
                    persona_id=persona.id,
                    duration_ms=round((time.perf_counter() - started_at) * 1000),
                    items_count=len(items),
                )
            except Exception as exc:
                logger.error(
                    "plan_persona_generation_failed",
                    persona_id=persona.id,
                    error=str(exc),
                    duration_ms=round((time.perf_counter() - started_at) * 1000),
                )
                async with rls_connection(claims) as conn:
                    await PlansRepo(conn).update_job_persona_status(
                        job_id, persona.id, "failed", last_error=str(exc)[:500]
                    )

    async def _generate_for_persona(
        self,
        *,
        persona: Any,
        columns: list[str],
        skeleton: dict[str, Any],
        results_summary: str,
        user_profile_summary: str,
        plan: Any,
        semaphore: asyncio.Semaphore | None,
        user_brief: str | None = None,
    ) -> list[dict[str, Any]]:
        if semaphore is not None:
            async with semaphore:
                return await self._generate_for_persona_inner(
                    persona=persona,
                    columns=columns,
                    skeleton=skeleton,
                    results_summary=results_summary,
                    user_profile_summary=user_profile_summary,
                    plan=plan,
                    user_brief=user_brief,
                )
        return await self._generate_for_persona_inner(
            persona=persona,
            columns=columns,
            skeleton=skeleton,
            results_summary=results_summary,
            user_profile_summary=user_profile_summary,
            plan=plan,
            user_brief=user_brief,
        )

    async def _generate_for_persona_inner(
        self,
        *,
        persona: Any,
        columns: list[str],
        skeleton: dict[str, Any],
        results_summary: str,
        user_profile_summary: str,
        plan: Any,
        user_brief: str | None = None,
    ) -> list[dict[str, Any]]:
        template_safety: str | None = None
        if persona.base_template_id:
            async with service_role_connection() as sconn:
                template_safety = await PersonaTemplatesRepo(sconn).get_safety_prompt(persona.base_template_id)
        persona_block = build_system_prompt(
            persona.system_prompt,
            template_safety_prompt=template_safety,
            persona_type=persona.type,
        )
        system_message = (
            f"{persona_block}\n\n"
            f"Wygeneruj plan typu '{plan.period_type}' dla okresu "
            f"{plan.start_date.isoformat()}..{plan.end_date.isoformat()}. Kolumny do "
            f"wypełnienia w każdym wierszu (W TEJ KOLEJNOŚCI): {columns}. "
            f"Wspólny szkielet od koordynatora (priorytet: spójność z innymi "
            f"personami): {skeleton}. Twarde ograniczenia persony: "
            f"{persona.persona_constraints or 'brak'}."
            f"{_format_user_brief_block(user_brief)}"
        )
        user_message = f"Profil użytkownika: {user_profile_summary}\nOstatnie wyniki: {results_summary}"
        result = await self._llm_client.complete_json(
            model=self._planner_model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            json_schema=_persona_items_schema(),
            max_tokens=self._persona_output_budget(plan.period_type),
        )
        items = []
        for raw_item in result.get("items", []):
            item_date = _parse_date(raw_item["item_date"])
            if item_date is None or not (plan.start_date <= item_date <= plan.end_date):
                continue
            content = rows_to_content(
                title=raw_item.get("title", persona.name),
                columns=columns,
                rows=raw_item.get("rows", []),
                notes=raw_item.get("notes"),
            )
            items.append(
                {
                    "item_date": item_date,
                    "item_type": persona.type,
                    "persona_id": persona.id,
                    "content": content,
                }
            )
        return items

    async def _run_harmonization(
        self,
        *,
        succeeded_personas: list[Any],
        item_lookup: dict[tuple[str, str], PlanItemRow],
        plan: Any,
        claims: dict,
        user_brief: str | None = None,
    ) -> None:
        if not item_lookup and not user_brief:
            return

        # Deterministic brief enforcement (e.g. remove all badminton_coach cards).
        if user_brief:
            excluded_ids = {p.id for p in succeeded_personas if plan_brief_excludes_persona_type(user_brief, p.type)}
            if excluded_ids:
                async with rls_connection(claims) as conn:
                    plans_repo = PlansRepo(conn)
                    for key, item in list(item_lookup.items()):
                        if item.persona_id in excluded_ids:
                            await plans_repo.delete_item(item.id)
                            item_lookup.pop(key, None)

        if not item_lookup:
            return

        persona_ids = [p.id for p in succeeded_personas]
        if not persona_ids:
            return

        draft_summary = "\n".join(
            f"- persona_id={item.persona_id} date={item.item_date.isoformat()} "
            f"title={item.content.get('title')} rows={item.content.get('rows')}"
            for item in item_lookup.values()
        )
        personas_context = "\n".join(f"- id={p.id} typ={p.type}: {p.system_prompt[:200]}" for p in succeeded_personas)
        system_message = (
            "Jesteś Goat — Kierownikiem Zespołu. Masz OSTATECZNY GŁOS nad planem. "
            "Dostałeś DRAFT od trenerów. Wykryj konflikty (ciężki trening + długi bieg tego "
            "samego dnia, dieta niedopasowana, brak regeneracji) i zwróć TARGETED PATCHE "
            "(persona_id + item_date). action=update zmienia treść; action=delete usuwa kartę "
            "(np. gdy brief usera wyklucza dyscyplinę albo karta jest zbędna). "
            "NIE regeneruj wszystkiego. Jeśli draft spójny — pusta lista patches. "
            f"Persony:\n{personas_context}"
            f"{_format_user_brief_block(user_brief)}"
        )
        user_message = f"Draft planu:\n{draft_summary}"

        started_at = time.perf_counter()
        result = await self._llm_client.complete_json(
            model=self._planner_model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            json_schema=_harmonization_schema(persona_ids),
            max_tokens=settings.plan_harmonization_max_output_tokens,
        )
        logger.info(
            "plan_stage_completed",
            stage="harmonization",
            duration_ms=round((time.perf_counter() - started_at) * 1000),
            draft_item_count=len(item_lookup),
        )

        patches = result.get("patches", [])
        if not patches:
            return

        async with rls_connection(claims) as conn:
            plans_repo = PlansRepo(conn)
            for patch in patches:
                key = (patch["persona_id"], patch["item_date"])
                maybe_item = item_lookup.get(key)
                if maybe_item is None:
                    continue
                item = maybe_item
                action = str(patch.get("action") or "update")
                if action == "delete":
                    await plans_repo.delete_item(item.id)
                    item_lookup.pop(key, None)
                    continue
                columns = item.content.get("columns", [])
                content = rows_to_content(
                    title=patch.get("title") or item.content.get("title", ""),
                    columns=columns,
                    rows=patch.get("rows", []),
                    notes=patch.get("notes") or item.content.get("notes"),
                )
                await plans_repo.update_item_content(item.id, content)

    async def run_harmonize_for_dates(
        self,
        *,
        plan_id: str,
        user_id: str,
        claims: dict[str, Any],
        dates: list[str],
    ) -> None:
        """Light harmonization after `upsert_plan_items` — affected days only."""
        if not dates:
            return
        date_set = set(dates)
        async with rls_connection(claims) as conn:
            plans_repo = PlansRepo(conn)
            plan = await plans_repo.get_plan(plan_id)
            if plan is None:
                return
            items = await plans_repo.list_items_for_plan(plan_id)
            active_personas = await PersonasRepo(conn).list_active_for_user(user_id)

        item_lookup: dict[tuple[str, str], PlanItemRow] = {}
        persona_ids_seen: set[str] = set()
        for item in items:
            iso = item.item_date.isoformat()
            if iso not in date_set:
                continue
            item_lookup[(item.persona_id, iso)] = item
            persona_ids_seen.add(item.persona_id)

        succeeded_personas = [p for p in active_personas if p.id in persona_ids_seen]
        if not item_lookup or not succeeded_personas:
            return

        try:
            await self._run_harmonization(
                succeeded_personas=succeeded_personas,
                item_lookup=item_lookup,
                plan=plan,
                claims=claims,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("plan_lite_harmonization_failed", error=str(exc))


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _summarize_results(results: list[Any]) -> str:
    if not results:
        return "brak zalogowanych wyników"
    lines = [f"{r.logged_date.isoformat()} {r.category}/{r.metric}={r.value}{r.unit or ''}" for r in results[:30]]
    return "\n".join(lines)


def _summarize_user_profile(profile: Any) -> str:
    if profile is None:
        return "brak danych profilu (nieuzupełniony)"
    parts = []
    if profile.height_cm:
        parts.append(f"wzrost {profile.height_cm}cm")
    if profile.weight_kg:
        parts.append(f"waga {profile.weight_kg}kg")
    if profile.activity_level:
        parts.append(f"aktywność {profile.activity_level}")
    if profile.primary_goal:
        parts.append(f"cel {profile.primary_goal}")
    return ", ".join(parts) if parts else "brak danych profilu (nieuzupełniony)"
