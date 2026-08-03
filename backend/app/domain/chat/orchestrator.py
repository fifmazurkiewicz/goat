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
from app.core.db import rls_connection
from app.core.dependencies import get_moderation_service, get_pricing_cache
from app.core.exceptions import AppError, ConflictError, NotFoundError, ValidationError
from app.domain.chat.context_builder import ContextBuilder
from app.domain.chat.routing import ChatRoutingService, RoutingResult
from app.domain.chat.tools import get_chat_tools
from app.domain.results.metrics_cache import allowed_metrics_cache
from app.domain.results.service import ResultsService
from app.domain.usage.service import UsageLimitService
from app.llm.openrouter_client import get_openrouter_client
from app.llm.tool_calling import ToolCallBuffer
from app.models.schemas import LogResultArgs, UserProfileOut, UserProfileUpdate
from app.repositories.chat_repo import ChatRepo
from app.repositories.personas_repo import PersonasRepo
from app.repositories.profiles_repo import ProfilesRepo
from app.repositories.results_repo import ResultsRepo
from app.repositories.usage_limits_repo import UsageLimitsRepo
from app.repositories.user_profile_repo import UserProfileRepo

logger = structlog.get_logger(__name__)


class LLMClientProtocol(Protocol):
    async def stream_chat(
        self, *, model: str, messages: list[dict[str, Any]], **kwargs: Any
    ) -> Any: ...


async def _emit(queue: asyncio.Queue[dict[str, Any]], event: str, data: dict[str, Any]) -> None:
    await queue.put({"event": event, "data": json.dumps(data, default=str)})


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

    async def handle_message(
        self,
        *,
        user_id: str,
        session_id: str,
        session_type: str,
        persona: Any,
        user_message: str,
        queue: asyncio.Queue[dict[str, Any]],
    ) -> None:
        """Obsługuje jedną turę: persona JUŻ wybrana (routing — jeśli dotyczy — zaszedł
        PRZED wywołaniem tej metody, patrz `run_chat_turn` poniżej i ADR-13)."""
        try:
            await self._handle_message_inner(
                user_id=user_id,
                session_id=session_id,
                session_type=session_type,
                persona=persona,
                user_message=user_message,
                queue=queue,
            )
        except asyncio.CancelledError:
            raise
        except AppError as exc:
            await _emit(queue, "error", {"code": exc.code, "message": exc.message})
            await queue.put({"event": "done", "data": "{}"})
        except Exception as exc:  # noqa: BLE001 — top-level safety net dla producer taska
            logger.error("chat_orchestrator_unexpected_error", error=str(exc), exc_info=exc)
            await _emit(
                queue,
                "error",
                {"code": "internal_error", "message": "Wystąpił nieoczekiwany błąd czatu."},
            )
            await queue.put({"event": "done", "data": "{}"})

    async def _handle_message_inner(
        self,
        *,
        user_id: str,
        session_id: str,
        session_type: str,
        persona: Any,
        user_message: str,
        queue: asyncio.Queue[dict[str, Any]],
    ) -> None:
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

        async with rls_connection(self._claims) as conn:
            context_builder = ContextBuilder(
                ChatRepo(conn), history_window_messages=settings.chat_history_window_messages
            )
            user_profile_row = await UserProfileRepo(conn).get(user_id)
            user_profile = (
                UserProfileOut.model_validate(user_profile_row) if user_profile_row else None
            )
            system_prompt = context_builder.build_system_prompt(
                persona_system_prompt=persona.system_prompt,
                persona_constraints=persona.persona_constraints,
                user_profile=user_profile,
            )
            history = await context_builder.build_message_history(
                session_id=session_id, session_type=session_type, persona_id=persona.id
            )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": user_message},
        ]
        tools = get_chat_tools()
        fallback_models = [
            m.strip()
            for m in settings.openrouter_chat_model_fallbacks.split(",")
            if m.strip()
        ]

        for round_index in range(settings.chat_max_tool_rounds):
            period_start = await self._reserve_round_budget(
                user_id=user_id, model=persona.chat_model, prompt=messages
            )

            content_buffer: list[str] = []
            tool_buffers: dict[int, ToolCallBuffer] = {}
            finish_reason: str | None = None
            usage_chunk: dict[str, Any] | None = None
            emitted_tool_call_start = False

            async for chunk in self._llm_client.stream_chat(
                model=persona.chat_model,
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
                    content_buffer.append(delta["content"])
                    await _emit(queue, "token", {"text": delta["content"]})

                for tool_call_delta in delta.get("tool_calls") or []:
                    index = tool_call_delta.get("index", 0)
                    buffer = tool_buffers.setdefault(index, ToolCallBuffer())
                    buffer.accumulate(tool_call_delta)
                    if not emitted_tool_call_start and buffer.name:
                        emitted_tool_call_start = True
                        await _emit(
                            queue, "tool_call_start", {"name": buffer.name, "persona_id": persona.id}
                        )

            actual_cost = await self._reconcile_round_cost(
                user_id=user_id,
                model=persona.chat_model,
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
                )
                messages.extend(tool_response_messages)

                async with rls_connection(self._claims) as conn:
                    await ChatRepo(conn).touch_session(session_id)
                continue

            # finish_reason == 'stop' (albo brak dalszych tool calls) -> koniec tury.
            async with rls_connection(self._claims) as conn:
                chat_repo = ChatRepo(conn)
                await chat_repo.insert_assistant_message(
                    session_id=session_id,
                    content=assistant_content,
                    tool_calls=None,
                    persona_id=persona.id,
                )
                await chat_repo.touch_session(session_id)

            await queue.put({"event": "done", "data": "{}"})
            return

        # Twardy limit rund osiągnięty bez finish_reason=='stop' — bezpiecznik przeciw
        # pętlom (security.md §4), NIE oczekiwana ścieżka normalnego użycia (ADR-6:
        # log_result batch sprawia że 3-5 rund wystarcza na realistyczne scenariusze).
        logger.warning("chat_max_tool_rounds_reached", session_id=session_id)
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
    ) -> list[dict[str, Any]]:
        async with rls_connection(self._claims) as conn:
            chat_repo = ChatRepo(conn)
            await chat_repo.insert_assistant_message(
                session_id=session_id,
                content=assistant_content,
                tool_calls=tool_calls_payload,
                persona_id=persona.id,
            )

            results_service = ResultsService(ResultsRepo(conn), allowed_metrics_cache)
            user_profile_repo = UserProfileRepo(conn)

            tool_response_messages: list[dict[str, Any]] = []
            for call in tool_calls_payload:
                name = call["function"]["name"]
                raw_arguments = call["function"]["arguments"]
                tool_call_id = call["id"]

                response_content = await self._run_single_tool(
                    name=name,
                    raw_arguments=raw_arguments,
                    user_id=user_id,
                    persona_id=persona.id,
                    results_service=results_service,
                    user_profile_repo=user_profile_repo,
                )

                await chat_repo.insert_tool_message(
                    session_id=session_id,
                    tool_call_id=tool_call_id,
                    content=response_content,
                    persona_id=persona.id,
                )
                await _emit(
                    queue,
                    "tool_result",
                    {"name": name, "persona_id": persona.id, "result": response_content},
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
        persona_id: str,
        results_service: ResultsService,
        user_profile_repo: UserProfileRepo,
    ) -> str:
        """Błąd walidacji (JSON niepoprawny / Pydantic) wraca jako tool response, NIGDY
        wyjątek serwera (security.md §3) — niezaufany input mimo że pochodzi z modelu."""
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

        return json.dumps({"error": f"Nieznane narzędzie: {name!r}"})


async def run_chat_turn(
    *,
    user_id: str,
    claims: dict[str, Any],
    session_id: str,
    user_message: str,
    queue: asyncio.Queue[dict[str, Any]],
) -> None:
    """Funkcja producent, uruchamiana jako `asyncio.create_task` z routera (architecture.md
    §3, `run_chat_orchestrator` w pseudokodzie tam). Odpowiada za:
    1. Rozwiązanie sesji + (jeśli `general`) ROUTING persony PRZED wywołaniem
       `ChatOrchestrator.handle_message` (ADR-13 — routing to krok POZA logiką pojedynczej
       persony, która pozostaje niezmieniona).
    2. Zapis wiadomości usera.
    3. Emisję `persona_turn_start` przed pierwszym tokenem tury.
    4. Delegację do `ChatOrchestrator.handle_message`.
    """
    llm_client = get_openrouter_client()

    async with rls_connection(claims) as conn:
        chat_repo = ChatRepo(conn)
        session = await chat_repo.get_session(session_id)
        if session is None or session.user_id != user_id:
            raise NotFoundError(f"Sesja czatu {session_id!r} nie istnieje.")

        personas_repo = PersonasRepo(conn)

        if session.session_type == "general":
            active_personas = await personas_repo.list_active_for_user(user_id)
            if not active_personas:
                raise ConflictError(
                    "Brak aktywnych person — dodaj przynajmniej jedną personę przed "
                    "rozpoczęciem ogólnej rozmowy."
                )
            routing_service = ChatRoutingService(
                llm_client, chat_repo, chat_model=settings.openrouter_chat_model
            )
            routing: RoutingResult = await routing_service.route(
                session_id=session_id, message=user_message, active_personas=active_personas
            )
            persona = next(p for p in active_personas if p.id == routing.persona_id)
            content = routing.content
            invoked_via: str | None = routing.invoked_via
        else:
            persona = await personas_repo.get_visible(session.persona_id)  # type: ignore[arg-type]
            if persona is None:
                raise NotFoundError("Persona przypisana do sesji nie istnieje.")
            content = user_message
            invoked_via = None

        if len(content.strip()) == 0:
            raise ValidationError("Wiadomość nie może być pusta po usunięciu prefiksu /slug.")
        if len(content) > settings.chat_max_message_length:
            content = content[: settings.chat_max_message_length]

        await chat_repo.insert_user_message(
            session_id=session_id, content=content, persona_id=None, invoked_via=invoked_via
        )

    await _emit(queue, "persona_turn_start", {"persona_id": persona.id, "persona_label": persona.name})

    orchestrator = ChatOrchestrator(llm_client, claims)
    await orchestrator.handle_message(
        user_id=user_id,
        session_id=session_id,
        session_type=session.session_type,
        persona=persona,
        user_message=content,
        queue=queue,
    )
