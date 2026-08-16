"""`ChatOrchestrator` — pętla SSE + multi-turn tool calling (architecture.md sekcja 3).

**Wyjątek architektoniczny (dokumentowany, świadomy):** w przeciwieństwie do innych
serwisów domenowych (`PersonaService`, `ResultsService`...), które dostają repo już
związane z JEDNYM połączeniem DB przez konstruktor, `ChatOrchestrator` MUSI samo
zarządzać cyklem życia wielu KRÓTKICH połączeń w trakcie długiego streamu (architecture.md
§3: "połączenie DB nie może żyć przez cały czas streamu... orkiestrator otwiera krótkie
transakcje tylko na moment zapisu, per rundę"). Stąd ten moduł zna konkretne repo i
`app.core.db.rls_connection` zamiast czystych `Protocol` z DI przez konstruktor — jedyne
takie miejsce obok `PlanOrchestrator` (ten sam powód: `BackgroundTasks` + wiele
równoległych połączeń).
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any, Protocol

import structlog
from pydantic import ValidationError as PydanticValidationError

from app.core.config import settings
from app.core.db import rls_connection, service_role_connection
from app.core.dependencies import get_moderation_service, get_pricing_cache
from app.core.exceptions import AppError, ConflictError, NotFoundError, ValidationError
from app.domain.chat.context_builder import ContextBuilder
from app.domain.chat.plan_tools import ChatPlanToolsService
from app.domain.chat.routing import parse_multi_slash_command
from app.domain.chat.team_lead import (
    MAX_CONSULTS_PER_TURN,
    TEAM_LEAD_DISPLAY_LABEL,
    TeamLeadSpeaker,
    build_goat_turn_prompt,
    goat_consult_status_message,
    persona_display_label,
    resolve_persona_by_slug,
)
from app.domain.chat.tools import (
    TEAM_LEAD_CHAT_TOOL_NAMES,
    get_team_lead_plan_tools,
    get_trainer_chat_tools,
)
from app.domain.jobs.runner import enqueue_chat_title_async
from app.domain.results.metrics_cache import allowed_metrics_cache
from app.domain.results.service import ResultsService
from app.domain.usage.service import UsageLimitService
from app.llm.openrouter_client import get_openrouter_client
from app.llm.tool_calling import ToolCallBuffer
from app.models.schemas import LogResultArgs, UserProfileOut, UserProfileUpdate
from app.repositories.chat_repo import ChatRepo
from app.repositories.personas_repo import PersonasRepo
from app.repositories.plans_repo import PlansRepo
from app.repositories.profiles_repo import ProfilesRepo
from app.repositories.results_repo import ResultsRepo
from app.repositories.templates_repo import PersonaTemplatesRepo
from app.repositories.usage_limits_repo import UsageLimitsRepo
from app.repositories.user_profile_repo import UserProfileRepo

logger = structlog.get_logger(__name__)


def _title_from_message(text: str, *, max_len: int = 60) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def should_run_goat_turn(message: str, active_personas: list[Any]) -> bool:
    """Sesja general bez `/slug` — mówi wyłącznie Goat (GWT-1); slash → False (GWT-5)."""
    return parse_multi_slash_command(message, active_personas) is None


class LLMClientProtocol(Protocol):
    async def stream_chat(
        self, *, model: str, messages: list[dict[str, Any]], **kwargs: Any
    ) -> Any: ...


async def _emit(queue: asyncio.Queue[dict[str, Any]], event: str, data: dict[str, Any]) -> None:
    await queue.put({"event": event, "data": json.dumps(data, default=str, ensure_ascii=False)})


_PERSONA_PHASE_MESSAGES: dict[str, str] = {
    "thinking": "{name} analizuje Twoje pytanie…",
    "writing": "{name} formułuje odpowiedź…",
    "tool": "{name} {action}…",
    "wrapping_up": "{name} kończy odpowiedź…",
    "done": "{name} zakończył(a) odpowiedź",
}


async def _emit_persona_status(
    queue: asyncio.Queue[dict[str, Any]],
    *,
    persona: Any,
    phase: str,
    message: str | None = None,
    tool_name: str | None = None,
    label: str | None = None,
) -> None:
    display = label or (
        TEAM_LEAD_DISPLAY_LABEL
        if getattr(persona, "type", None) == "team_lead"
        else persona_display_label(persona)
    )
    persona_id = None if getattr(persona, "type", None) == "team_lead" else persona.id
    if message is None:
        template = _PERSONA_PHASE_MESSAGES.get(phase, "{name} pracuje…")
        action = ""
        if phase == "tool" and tool_name:
            labels = {
                "log_result": "zapisuje wynik",
                "update_user_profile": "aktualizuje profil",
                "get_plan": "przegląda plan",
                "upsert_plan_items": "zapisuje w Plany",
                "rebuild_plan": "uzgadnia plan",
            }
            action = labels.get(tool_name, "wykonuje akcję")
        message = template.format(name=display.split(" · ")[0], action=action)
    await _emit(
        queue,
        "persona_status",
        {
            "persona_id": persona_id,
            "persona_label": display,
            "phase": phase,
            "message": message,
            **({"tool_name": tool_name} if tool_name else {}),
        },
    )


def _persist_persona_id(persona: Any) -> str | None:
    return None if getattr(persona, "type", None) == "team_lead" else persona.id


def _tool_result_event_payload(name: str, response_content: str) -> dict[str, Any]:
    """Kontrakt FE (`tool_name`/`summary`/`success`) — nie surowy JSON tool response."""
    summary = "Wykonano narzędzie"
    success = True
    job_id: str | None = None
    try:
        parsed = json.loads(response_content) if response_content else {}
    except json.JSONDecodeError:
        parsed = {}
    if isinstance(parsed, dict):
        if parsed.get("error"):
            summary = str(parsed["error"])
            success = False
        elif name == "update_user_profile":
            fields = parsed.get("updated_fields") or []
            summary = (
                f"Zaktualizowano profil: {', '.join(fields)}"
                if fields
                else "Profil bez zmian"
            )
            success = parsed.get("status") != "error"
        elif name == "log_result":
            results = parsed.get("results") or []
            ok = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "ok")
            failed = len(results) - ok
            if failed:
                summary = f"Zapisano {ok}, błędów: {failed}"
                success = False
            else:
                summary = "Zapisano wynik" if ok == 1 else f"Zapisano {ok} wyników"
        elif name == "get_plan":
            if parsed.get("status") == "empty":
                summary = "Brak planu w kalendarzu"
            else:
                n = len(parsed.get("items") or [])
                summary = f"Plan: {n} pozycji"
            success = parsed.get("status") != "error"
        elif name == "upsert_plan_items":
            n = int(parsed.get("upserted") or 0)
            summary = f"Zapisano {n} pozycji w Plany" if n else "Nie zapisano pozycji planu"
            success = parsed.get("status") in ("ok", "partial")
        elif name == "rebuild_plan":
            job_id = str(parsed["job_id"]) if parsed.get("job_id") else None
            summary = (
                f"Uruchomiono przebudowę planu"
                + (f" (job {job_id[:8]}…)" if job_id else "")
            )
            success = parsed.get("status") == "ok"
        elif name == "consult_persona":
            if parsed.get("error"):
                summary = str(parsed["error"])
                success = False
            else:
                label = str(parsed.get("persona_label") or parsed.get("slug") or "")
                summary = f"Skonsultowano: {label}" if label else "Skonsultowano trenera"
                success = parsed.get("status") == "ok"
        elif response_content:
            summary = response_content[:80] + ("…" if len(response_content) > 80 else "")
    payload: dict[str, Any] = {"tool_name": name, "summary": summary, "success": success}
    if job_id:
        payload["job_id"] = job_id
    return payload


class ChatOrchestrator:
    """Producer strony agregatora SSE — wypełnia `asyncio.Queue` konsumowaną przez
    endpoint `/chat` (`sse-starlette` `EventSourceResponse`, patrz api/routers/chat.py).

    `claims` — JWT claims zalogowanego usera, zbindowane per-instancję (jedna instancja
    per request/wiadomość, tworzona w routerze) — używane do otwierania krótkich
    `rls_connection` w trakcie pętli.
    """

    def __init__(self, llm_client: LLMClientProtocol, claims: dict[str, Any]) -> None:
        self._llm_client = llm_client
        self._claims = claims
        self._consult_roster: list[Any] | None = None
        self._consult_count: int = 0
        self._consult_session_id: str | None = None
        self._consult_user_queue: asyncio.Queue[dict[str, Any]] | None = None

    async def handle_message(
        self,
        *,
        user_id: str,
        session_id: str,
        session_type: str,
        persona: Any,
        user_message: str,
        queue: asyncio.Queue[dict[str, Any]],
        emit_done: bool = True,
        allowed_persona_ids: list[str] | None = None,
        client_visible: bool = True,
        status_label: str | None = None,
        emit_sse: bool = True,
        persist_messages: bool = True,
        consult_roster: list[Any] | None = None,
    ) -> tuple[bool, str | None]:
        """Obsługuje jedną turę persony. Zwraca `(sukces, treść odpowiedzi assistant)`."""
        try:
            return await self._handle_message_inner(
                user_id=user_id,
                session_id=session_id,
                session_type=session_type,
                persona=persona,
                user_message=user_message,
                queue=queue,
                emit_done=emit_done,
                allowed_persona_ids=allowed_persona_ids,
                client_visible=client_visible,
                status_label=status_label,
                emit_sse=emit_sse,
                persist_messages=persist_messages,
                consult_roster=consult_roster,
            )
        except asyncio.CancelledError:
            raise
        except AppError as exc:
            if emit_sse:
                await _emit(queue, "error", {"code": exc.code, "message": exc.message})
                await queue.put({"event": "done", "data": "{}"})
            return False, None
        except Exception as exc:  # noqa: BLE001 — top-level safety net dla producer taska
            logger.error("chat_orchestrator_unexpected_error", error=str(exc), exc_info=exc)
            if emit_sse:
                await _emit(
                    queue,
                    "error",
                    {"code": "internal_error", "message": "Wystąpił nieoczekiwany błąd czatu."},
                )
                await queue.put({"event": "done", "data": "{}"})
            return False, None

    async def _handle_message_inner(
        self,
        *,
        user_id: str,
        session_id: str,
        session_type: str,
        persona: Any,
        user_message: str,
        queue: asyncio.Queue[dict[str, Any]],
        emit_done: bool = True,
        allowed_persona_ids: list[str] | None = None,
        client_visible: bool = True,
        status_label: str | None = None,
        emit_sse: bool = True,
        persist_messages: bool = True,
        consult_roster: list[Any] | None = None,
    ) -> tuple[bool, str | None]:
        if consult_roster is not None:
            self._consult_roster = consult_roster
            self._consult_session_id = session_id
            self._consult_user_queue = queue
        # Warstwa C (security.md §1) — świadomie fail-open: `check_chat_message` już
        # zaloguje trafienie do `moderation_events` (do przeglądu), ale NIE blokujemy tu
        # samej wiadomości. Preambuł platformy (warstwa A) + odporność samego modelu na
        # instrukcje w treści usera są pierwszą linią obrony; twarde blokowanie na samej
        # heurystyce/klasyfikatorze niosłoby zbyt duże ryzyko false-positive (zwykłe
        # pytanie o "zasady treningu" zawiera słowo "zasady") i psuło UX. Jeśli w
        # przyszłości potrzebna twarda blokada, tu jest jedyne miejsce do dodania.
        await get_moderation_service().check_chat_message(
            user_id=user_id, message=user_message, session_id=session_id
        )

        template_safety: str | None = None
        if persona.type != "team_lead" and persona.base_template_id:
            async with service_role_connection() as sconn:
                template_safety = await PersonaTemplatesRepo(sconn).get_safety_prompt(
                    persona.base_template_id
                )

        async with rls_connection(self._claims) as conn:
            context_builder = ContextBuilder(
                ChatRepo(conn), history_window_messages=settings.chat_history_window_messages
            )
            user_profile_row = await UserProfileRepo(conn).get(user_id)
            user_profile = (
                UserProfileOut.model_validate(user_profile_row) if user_profile_row else None
            )
            plans_repo = PlansRepo(conn)
            plan_row = await plans_repo.get_latest_editable_plan_for_user(user_id)
            plan_items: list[Any] = []
            if plan_row is not None:
                plan_items = await plans_repo.list_items_for_plan(plan_row.id)
            recent_results = await ResultsRepo(conn).list_recent_for_user(limit=12)
            system_prompt = context_builder.build_system_prompt(
                persona_type=persona.type,
                persona_system_prompt=persona.system_prompt,
                persona_constraints=persona.persona_constraints,
                user_profile=user_profile,
                template_safety_prompt=template_safety,
                recent_results=recent_results,
                plan_row=plan_row,
                plan_items=plan_items,
            )
            history = await context_builder.build_message_history(
                session_id=session_id,
                session_type=session_type,
                persona_id=None if persona.type == "team_lead" else persona.id,
            )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": user_message},
        ]
        tools = get_team_lead_plan_tools() if persona.type == "team_lead" else get_trainer_chat_tools()
        fallback_models = [
            m.strip()
            for m in settings.openrouter_chat_model_fallbacks.split(",")
            if m.strip()
        ]
        chat_model = settings.openrouter_chat_model

        if emit_sse:
            await _emit_persona_status(
                queue,
                persona=persona,
                phase="thinking",
                label=status_label,
            )
        emitted_writing_status = False

        for round_index in range(settings.chat_max_tool_rounds):
            period_start = await self._reserve_round_budget(
                user_id=user_id, model=chat_model, prompt=messages
            )

            content_buffer: list[str] = []
            tool_buffers: dict[int, ToolCallBuffer] = {}
            finish_reason: str | None = None
            usage_chunk: dict[str, Any] | None = None
            emitted_tool_call_start = False

            async for chunk in self._llm_client.stream_chat(
                model=chat_model,
                messages=messages,
                tools=tools,
                max_tokens=settings.chat_max_output_tokens,
                fallback_models=fallback_models,
            ):
                if chunk.get("usage"):
                    usage_chunk = chunk["usage"]
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]
                delta = choice.get("delta") or {}
                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]

                if delta.get("content"):
                    if not emitted_writing_status:
                        emitted_writing_status = True
                        if emit_sse:
                            await _emit_persona_status(
                                queue, persona=persona, phase="writing", label=status_label
                            )
                    content_buffer.append(delta["content"])
                    if emit_sse and client_visible:
                        await _emit(queue, "token", {"text": delta["content"]})

                for tool_call_delta in delta.get("tool_calls") or []:
                    index = tool_call_delta.get("index", 0)
                    buffer = tool_buffers.setdefault(index, ToolCallBuffer())
                    buffer.accumulate(tool_call_delta)
                    if not emitted_tool_call_start and buffer.name:
                        emitted_tool_call_start = True
                        if emit_sse:
                            await _emit(
                                queue,
                                "tool_call_start",
                                {
                                    "name": buffer.name,
                                    "persona_id": (
                                        None
                                        if status_label
                                        else _persist_persona_id(persona)
                                    ),
                                },
                            )
                            if buffer.name != "consult_persona":
                                await _emit_persona_status(
                                    queue,
                                    persona=persona,
                                    phase="tool",
                                    tool_name=buffer.name,
                                    label=status_label,
                                )

            actual_cost = await self._reconcile_round_cost(
                user_id=user_id,
                model=chat_model,
                period_start=period_start,
                usage_chunk=usage_chunk,
            )
            logger.info("chat_round_completed", round=round_index, actual_cost_usd=actual_cost)

            assistant_content = "".join(content_buffer) or None

            if finish_reason == "tool_calls" and tool_buffers:
                tool_calls_payload = [
                    {
                        "id": buf.id or f"call_{idx}",
                        "type": "function",
                        "function": {"name": buf.name, "arguments": buf.get_arguments_json()},
                    }
                    for idx, buf in sorted(tool_buffers.items())
                ]
                messages.append(
                    {"role": "assistant", "content": assistant_content, "tool_calls": tool_calls_payload}
                )

                tool_response_messages = await self._execute_tool_calls(
                    user_id=user_id,
                    session_id=session_id,
                    persona=persona,
                    assistant_content=assistant_content,
                    tool_calls_payload=tool_calls_payload,
                    queue=queue,
                    allowed_persona_ids=allowed_persona_ids,
                    persist_messages=persist_messages,
                    emit_sse=emit_sse,
                )
                messages.extend(tool_response_messages)

                async with rls_connection(self._claims) as conn:
                    await ChatRepo(conn).touch_session(session_id)
                continue

            # finish_reason == 'stop' (albo brak dalszych tool calls) -> koniec tury.
            if emit_sse:
                await _emit_persona_status(
                    queue, persona=persona, phase="wrapping_up", label=status_label
                )
            if persist_messages and client_visible:
                async with rls_connection(self._claims) as conn:
                    chat_repo = ChatRepo(conn)
                    await chat_repo.insert_assistant_message(
                        session_id=session_id,
                        content=assistant_content,
                        tool_calls=None,
                        persona_id=_persist_persona_id(persona),
                    )
                    await chat_repo.touch_session(session_id)

            if emit_sse:
                await _emit_persona_status(queue, persona=persona, phase="done", label=status_label)
            if emit_done:
                if emit_sse:
                    await _emit(queue, "turn_complete", {})
                await queue.put({"event": "done", "data": "{}"})
            return True, assistant_content

        # Twardy limit rund osiągnięty bez finish_reason=='stop' — bezpiecznik przeciw
        # pętlom (security.md §4), NIE oczekiwana ścieżka normalnego użycia (ADR-6:
        # log_result batch sprawia że 3-5 rund wystarcza na realistyczne scenariusze).
        logger.warning("chat_max_tool_rounds_reached", session_id=session_id)
        if emit_sse:
            await _emit(
                queue,
                "error",
                {
                    "code": "max_rounds_exceeded",
                    "message": "Osiągnięto limit rund narzędzi w tej turze. Spróbuj sformułować "
                    "prośbę w jednej wiadomości.",
                },
            )
        await queue.put({"event": "done", "data": "{}"})
        return False, None

    async def _reserve_round_budget(
        self, *, user_id: str, model: str, prompt: list[dict[str, Any]]
    ) -> date:
        prompt_chars = sum(len(str(m.get("content") or "")) for m in prompt)
        async with rls_connection(self._claims) as conn:
            usage_service = UsageLimitService(
                UsageLimitsRepo(conn), ProfilesRepo(conn), get_pricing_cache()
            )
            estimated = await usage_service.estimate_turn_cost_usd(
                model=model,
                prompt_text_length_chars=prompt_chars,
                max_output_tokens=settings.chat_max_output_tokens,
            )
            return await usage_service.reserve_estimated_cost(
                user_id=user_id, estimated_cost_usd=estimated
            )

    async def _reconcile_round_cost(
        self,
        *,
        user_id: str,
        model: str,
        period_start: date,
        usage_chunk: dict[str, Any] | None,
    ) -> float:
        pricing_cache = get_pricing_cache()
        prompt_tokens = int((usage_chunk or {}).get("prompt_tokens", 0) or 0)
        completion_tokens = int((usage_chunk or {}).get("completion_tokens", 0) or 0)
        actual_cost = await pricing_cache.estimate_cost_usd(
            model=model, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
        )
        prompt_chars_estimate = 0  # rekoncyliacja koryguje wyłącznie różnicę kosztu, nie tokeny wejściowe
        async with rls_connection(self._claims) as conn:
            usage_service = UsageLimitService(
                UsageLimitsRepo(conn), ProfilesRepo(conn), pricing_cache
            )
            estimated = await usage_service.estimate_turn_cost_usd(
                model=model,
                prompt_text_length_chars=prompt_chars_estimate,
                max_output_tokens=settings.chat_max_output_tokens,
            )
            await usage_service.reconcile_actual_cost(
                user_id=user_id,
                period_start=period_start,
                estimated_cost_usd=estimated,
                actual_cost_usd=actual_cost,
                actual_tokens=prompt_tokens + completion_tokens,
            )
        return actual_cost

    async def _execute_tool_calls(
        self,
        *,
        user_id: str,
        session_id: str,
        persona: Any,
        assistant_content: str | None,
        tool_calls_payload: list[dict[str, Any]],
        queue: asyncio.Queue[dict[str, Any]],
        allowed_persona_ids: list[str] | None = None,
        persist_messages: bool = True,
        emit_sse: bool = True,
    ) -> list[dict[str, Any]]:
        if persist_messages:
            async with rls_connection(self._claims) as conn:
                await ChatRepo(conn).insert_assistant_message(
                    session_id=session_id,
                    content=assistant_content,
                    tool_calls=tool_calls_payload,
                    persona_id=_persist_persona_id(persona),
                )

        tool_response_messages: list[dict[str, Any]] = []
        for call in tool_calls_payload:
            name = call["function"]["name"]
            raw_arguments = call["function"]["arguments"]
            tool_call_id = call["id"]

            if name == "consult_persona":
                # Nested LLM (30–90s) must not hold the parent RLS transaction.
                response_content = await self._run_single_tool(
                    name=name,
                    raw_arguments=raw_arguments,
                    user_id=user_id,
                    persona=persona,
                    results_service=None,
                    user_profile_repo=None,
                    plan_tools=None,
                    allowed_persona_ids=allowed_persona_ids,
                )
            else:
                async with rls_connection(self._claims) as conn:
                    response_content = await self._run_single_tool(
                        name=name,
                        raw_arguments=raw_arguments,
                        user_id=user_id,
                        persona=persona,
                        results_service=ResultsService(ResultsRepo(conn), allowed_metrics_cache),
                        user_profile_repo=UserProfileRepo(conn),
                        plan_tools=ChatPlanToolsService(conn, claims=self._claims),
                        allowed_persona_ids=allowed_persona_ids,
                    )
                    if persist_messages:
                        await ChatRepo(conn).insert_tool_message(
                            session_id=session_id,
                            tool_call_id=tool_call_id,
                            content=response_content,
                            persona_id=_persist_persona_id(persona),
                        )

            if persist_messages and name == "consult_persona":
                async with rls_connection(self._claims) as conn:
                    await ChatRepo(conn).insert_tool_message(
                        session_id=session_id,
                        tool_call_id=tool_call_id,
                        content=response_content,
                        persona_id=_persist_persona_id(persona),
                    )
            if emit_sse:
                await _emit(
                    queue,
                    "tool_result",
                    _tool_result_event_payload(name, response_content),
                )
            tool_response_messages.append(
                {"role": "tool", "tool_call_id": tool_call_id, "content": response_content}
            )

        return tool_response_messages

    async def _run_single_tool(
        self,
        *,
        name: str,
        raw_arguments: str,
        user_id: str,
        persona: Any,
        results_service: ResultsService | None = None,
        user_profile_repo: UserProfileRepo | None = None,
        plan_tools: ChatPlanToolsService | None = None,
        allowed_persona_ids: list[str] | None = None,
    ) -> str:
        """Błąd walidacji (JSON niepoprawny / Pydantic) wraca jako tool response, NIGDY
        wyjątek serwera (security.md §3) — niezaufany input mimo że pochodzi z modelu."""
        if name == "consult_persona":
            if getattr(persona, "type", None) != "team_lead":
                return json.dumps(
                    {"error": "consult_persona dostępne tylko dla Goata."},
                    ensure_ascii=False,
                )
            return await self._consult_persona(raw_arguments=raw_arguments, user_id=user_id)

        if getattr(persona, "type", None) == "team_lead" and name not in TEAM_LEAD_CHAT_TOOL_NAMES:
            return json.dumps(
                {"error": "Narzędzie niedostępne dla Kierownika Zespołu (Goat)."},
                ensure_ascii=False,
            )

        if results_service is None or user_profile_repo is None or plan_tools is None:
            return json.dumps({"error": f"Brak kontekstu DB dla narzędzia {name!r}."})

        persona_id = persona.id
        try:
            arguments = json.loads(raw_arguments) if raw_arguments else {}
        except json.JSONDecodeError as exc:
            return json.dumps({"error": f"Nieprawidłowy JSON argumentów: {exc}"})

        if name == "log_result":
            try:
                parsed = LogResultArgs.model_validate(arguments)
            except PydanticValidationError as exc:
                return json.dumps({"error": f"Nieprawidłowe argumenty log_result: {exc.errors()}"})

            entries = [
                {
                    "category": entry.category,
                    "metric": entry.metric,
                    "value": entry.value,
                    "unit": entry.unit,
                    "logged_date": entry.date,
                    "notes": entry.notes,
                }
                for entry in parsed.entries
            ]
            outcomes = await results_service.log_batch_from_agent(
                user_id=user_id, source_persona_id=persona_id, entries=entries
            )
            return json.dumps(
                {
                    "results": [
                        {"index": o.index, "status": "ok" if o.ok else "error", "error": o.error}
                        for o in outcomes
                    ]
                }
            )

        if name == "update_user_profile":
            try:
                parsed_profile = UserProfileUpdate.model_validate(arguments)
            except PydanticValidationError as exc:
                return json.dumps({"error": f"Nieprawidłowe argumenty update_user_profile: {exc.errors()}"})

            fields = parsed_profile.model_dump(exclude_unset=True)
            if not fields:
                return json.dumps({"status": "no_fields_provided"})
            await user_profile_repo.upsert(user_id, fields)
            return json.dumps({"status": "ok", "updated_fields": list(fields.keys())})

        if name == "get_plan":
            start = None
            end = None
            try:
                if arguments.get("start_date"):
                    start = date.fromisoformat(str(arguments["start_date"]))
                if arguments.get("end_date"):
                    end = date.fromisoformat(str(arguments["end_date"]))
            except ValueError as exc:
                return json.dumps({"error": f"Zła data: {exc}"})
            result = await plan_tools.get_plan(user_id=user_id, start_date=start, end_date=end)
            return json.dumps(result, default=str, ensure_ascii=False)

        if name == "upsert_plan_items":
            entries = arguments.get("entries")
            if not isinstance(entries, list) or not entries:
                return json.dumps({"error": "Wymagane entries: lista pozycji planu."})
            result = await plan_tools.upsert_plan_items(
                user_id=user_id,
                persona_id=persona_id,
                entries=entries,
                allowed_persona_ids=allowed_persona_ids,
            )
            return json.dumps(result, default=str, ensure_ascii=False)

        if name == "rebuild_plan":
            try:
                period_type = str(arguments["period_type"])
                start_date = date.fromisoformat(str(arguments["start_date"]))
            except (KeyError, ValueError, TypeError) as exc:
                return json.dumps({"error": f"Nieprawidłowe argumenty rebuild_plan: {exc}"})
            result = await plan_tools.rebuild_plan(
                user_id=user_id, period_type=period_type, start_date=start_date
            )
            return json.dumps(result, default=str, ensure_ascii=False)

        return json.dumps({"error": f"Nieznane narzędzie: {name!r}"})

    async def _consult_persona(self, *, raw_arguments: str, user_id: str) -> str:
        roster = self._consult_roster or []
        if self._consult_count >= MAX_CONSULTS_PER_TURN:
            return json.dumps(
                {"error": f"Limit {MAX_CONSULTS_PER_TURN} konsultacji w tej turze."},
                ensure_ascii=False,
            )
        try:
            arguments = json.loads(raw_arguments) if raw_arguments else {}
        except json.JSONDecodeError as exc:
            return json.dumps({"error": f"Nieprawidłowy JSON argumentów: {exc}"})
        slug = str(arguments.get("slug") or "").strip()
        question = str(arguments.get("question") or "").strip()
        if not slug or not question:
            return json.dumps({"error": "Wymagane slug i question."}, ensure_ascii=False)
        target = resolve_persona_by_slug(slug, roster)
        if target is None:
            return json.dumps(
                {"error": f"Brak aktywnej persony o slugu {slug!r}."},
                ensure_ascii=False,
            )
        self._consult_count += 1
        status = goat_consult_status_message(target)
        user_queue = self._consult_user_queue
        if user_queue is not None:
            await _emit_persona_status(
                user_queue,
                persona=TeamLeadSpeaker(),
                phase="tool",
                message=status,
                tool_name="consult_persona",
            )
        sink: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        ok, answer = await self.handle_message(
            user_id=user_id,
            session_id=self._consult_session_id or "",
            session_type="general",
            persona=target,
            user_message=question,
            queue=sink,
            emit_done=False,
            client_visible=False,
            emit_sse=False,
            persist_messages=False,
            allowed_persona_ids=[p.id for p in roster] if roster else None,
        )
        if not ok or not (answer or "").strip():
            return json.dumps(
                {"error": "Nie udało się skonsultować trenera.", "slug": slug},
                ensure_ascii=False,
            )
        label = persona_display_label(target)
        return json.dumps(
            {
                "status": "ok",
                "slug": target.slug,
                "persona_label": label,
                "answer": answer.strip(),
            },
            ensure_ascii=False,
        )


async def run_chat_turn(
    *,
    user_id: str,
    claims: dict[str, Any],
    session_id: str,
    user_message: str,
    queue: asyncio.Queue[dict[str, Any]],
    retry: bool = False,
) -> None:
    """Funkcja producent, uruchamiana jako `asyncio.create_task` z routera (architecture.md
    §3, `run_chat_orchestrator` w pseudokodzie tam). Odpowiada za:
    1. Rozwiązanie sesji + (jeśli `general`) ROUTING persony PRZED wywołaniem
       `ChatOrchestrator.handle_message` (ADR-13 — routing to krok POZA logiką pojedynczej
       persony, która pozostaje niezmieniona).
    2. Zapis wiadomości usera (pomijany przy `retry=True`, gdy ostatnia wiadomość usera
       ma tę samą treść — „Wyślij ponownie” po urwanym SSE).
    3. Emisję `persona_turn_start` przed pierwszym tokenem tury.
    4. Delegację do `ChatOrchestrator.handle_message`.
    """
    try:
        await _run_chat_turn_inner(
            user_id=user_id,
            claims=claims,
            session_id=session_id,
            user_message=user_message,
            queue=queue,
            retry=retry,
        )
    except asyncio.CancelledError:
        raise
    except AppError as exc:
        await _emit(queue, "error", {"code": exc.code, "message": exc.message})
        await queue.put({"event": "done", "data": "{}"})
    except Exception as exc:  # noqa: BLE001 — top-level safety net dla producer taska
        logger.error("run_chat_turn_unexpected_error", error=str(exc), exc_info=exc)
        await _emit(
            queue,
            "error",
            {"code": "internal_error", "message": "Wystąpił nieoczekiwany błąd czatu."},
        )
        await queue.put({"event": "done", "data": "{}"})


async def _run_chat_turn_inner(
    *,
    user_id: str,
    claims: dict[str, Any],
    session_id: str,
    user_message: str,
    queue: asyncio.Queue[dict[str, Any]],
    retry: bool,
) -> None:
    llm_client = get_openrouter_client()

    async with rls_connection(claims) as conn:
        await ChatRepo(conn).set_turn_in_progress(session_id, True)

    try:
        await _run_chat_turn_body(
            user_id=user_id,
            claims=claims,
            session_id=session_id,
            user_message=user_message,
            queue=queue,
            retry=retry,
            llm_client=llm_client,
        )
    finally:
        async with rls_connection(claims) as conn:
            await ChatRepo(conn).set_turn_in_progress(session_id, False)


async def _run_chat_turn_body(
    *,
    user_id: str,
    claims: dict[str, Any],
    session_id: str,
    user_message: str,
    queue: asyncio.Queue[dict[str, Any]],
    retry: bool,
    llm_client: Any,
) -> None:
    goat_turn = False
    active_personas: list[Any] = []

    async with rls_connection(claims) as conn:
        chat_repo = ChatRepo(conn)
        session = await chat_repo.get_session(session_id)
        if session is None or session.user_id != user_id:
            raise NotFoundError(f"Sesja czatu {session_id!r} nie istnieje.")

        personas_repo = PersonasRepo(conn)

        session_type = session.session_type
        personas_by_id: dict[str, Any] = {}
        persona_ids: list[str] = []
        content = user_message
        invoked_via: str | None = None

        if session_type == "general":
            active_personas = await personas_repo.list_active_for_user(user_id)
            if not active_personas:
                raise ConflictError(
                    "Brak aktywnych person — dodaj przynajmniej jedną personę przed "
                    "rozpoczęciem ogólnej rozmowy."
                )
            personas_by_id = {p.id: p for p in active_personas}
            slash_match = parse_multi_slash_command(user_message, active_personas)
            if slash_match is None:
                goat_turn = True
                content = user_message
                invoked_via = None
            else:
                matched, content = slash_match
                persona_ids = [p.id for p in matched]
                invoked_via = "multi_slash" if len(matched) > 1 else "slash_command"
        else:
            persona = await personas_repo.get_visible(session.persona_id)  # type: ignore[arg-type]
            if persona is None:
                raise NotFoundError("Persona przypisana do sesji nie istnieje.")
            personas_by_id = {persona.id: persona}
            persona_ids = [persona.id]
            content = user_message
            invoked_via = None

        if len(content.strip()) == 0:
            raise ValidationError("Wiadomość nie może być pusta po usunięciu prefiksu /slug.")
        if len(content) > settings.chat_max_message_length:
            content = content[: settings.chat_max_message_length]

        skip_insert = False
        if retry:
            last_user = await chat_repo.get_last_user_message(session_id)
            skip_insert = last_user is not None and (last_user.content or "") == content

        if not skip_insert:
            await chat_repo.insert_user_message(
                session_id=session_id, content=content, persona_id=None, invoked_via=invoked_via
            )
            if settings.chat_llm_title_enabled:
                await enqueue_chat_title_async(
                    session_id=session_id,
                    user_id=user_id,
                    claims=claims,
                    message=content,
                )
            else:
                await chat_repo.set_title_if_empty(session_id, _title_from_message(content))

    orchestrator = ChatOrchestrator(llm_client, claims)
    active_ids = list(personas_by_id.keys()) if session_type == "general" else None

    if goat_turn:
        goat = TeamLeadSpeaker(
            system_prompt=build_goat_turn_prompt(
                active_personas=active_personas, user_message=content
            )
        )
        orchestrator._consult_roster = list(active_personas)
        orchestrator._consult_count = 0
        orchestrator._consult_session_id = session_id
        orchestrator._consult_user_queue = queue
        await _emit(
            queue,
            "persona_turn_start",
            {"persona_id": None, "persona_label": TEAM_LEAD_DISPLAY_LABEL},
        )
        ok, _ = await orchestrator.handle_message(
            user_id=user_id,
            session_id=session_id,
            session_type="general",
            persona=goat,
            user_message=content,
            queue=queue,
            emit_done=False,
            allowed_persona_ids=active_ids,
            client_visible=True,
            emit_sse=True,
            persist_messages=True,
            consult_roster=list(active_personas),
        )
        await _emit(
            queue,
            "persona_turn_end",
            {"persona_id": None, "persona_label": TEAM_LEAD_DISPLAY_LABEL},
        )
        if ok:
            await _emit(queue, "turn_complete", {})
            await queue.put({"event": "done", "data": "{}"})
        return

    for persona_id in persona_ids:
        persona = personas_by_id.get(persona_id)
        if persona is None:
            raise NotFoundError(f"Persona {persona_id!r} z routingu nie istnieje.")

        display_label = persona_display_label(persona)
        await _emit(
            queue,
            "persona_turn_start",
            {"persona_id": persona.id, "persona_label": display_label},
        )
        ok, _ = await orchestrator.handle_message(
            user_id=user_id,
            session_id=session_id,
            session_type=session_type,
            persona=persona,
            user_message=content,
            queue=queue,
            emit_done=False,
            allowed_persona_ids=active_ids,
            client_visible=True,
        )
        if not ok:
            return
        await _emit(
            queue,
            "persona_turn_end",
            {"persona_id": persona.id, "persona_label": display_label},
        )

    await _emit(queue, "turn_complete", {})
    await queue.put({"event": "done", "data": "{}"})
