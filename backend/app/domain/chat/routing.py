"""Parsowanie slash / wspólne typy routingu sesji `general` (ADR-13).

**Produkcja:** tura Goata (`TeamLeadSpeaker` + `consult_persona`) albo slash
(`parse_multi_slash_command`) — ADR-17. Nie `plan_consultation`.

`ChatRoutingService` — **deprecated** (zastąpiony przez turę Goata + slash); moduł
zachowuje `parse_multi_slash_command`, `RoutingResult`, `PersonaLike`.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from typing import Literal, Protocol

import structlog

from app.domain.chat.persona_scope import ROUTING_CLASSIFIER_RULES, routing_persona_line

logger = structlog.get_logger(__name__)

_SLASH_PREFIX_RE = re.compile(r"^/([a-z0-9_]+)(?:\s+|$)")


class PersonaLike(Protocol):
    id: str
    type: str
    slug: str
    system_prompt: str


@dataclass(frozen=True, slots=True)
class RoutingResult:
    persona_ids: list[str]
    invoked_via: Literal["slash_command", "multi_slash", "auto_routed"]
    content: str  # treść bez prefiksów `/slug`


class RoutingLLMClientProtocol(Protocol):
    async def complete_json(
        self, *, model: str, messages: list[dict], json_schema: dict, max_tokens: int = 100
    ) -> dict: ...


class RoutingRepositoryProtocol(Protocol):
    async def get_last_responding_persona(self, session_id: str) -> str | None: ...


_ROUTING_JSON_SCHEMA_NAME = "persona_routing"


def _first_sentence(text: str, *, max_length: int = 200) -> str:
    stripped = text.strip()
    for sep in (".", "!", "?", "\n"):
        idx = stripped.find(sep)
        if idx != -1:
            return stripped[: idx + 1][:max_length]
    return stripped[:max_length]


def parse_multi_slash_command(
    message: str, active_personas: list[PersonaLike]
) -> tuple[list[PersonaLike], str] | None:
    """Wszystkie `/slug` na początku wiadomości (kolejność zachowana, dedupe po id).

    `None` gdy brak prefiksu `/`, nieznany slug w łańcuchu albo pusta treść po slugach.
    """
    text = message.strip()
    personas: list[PersonaLike] = []
    seen: set[str] = set()
    pos = 0
    while True:
        match = _SLASH_PREFIX_RE.match(text[pos:])
        if match is None:
            break
        slug = match.group(1)
        match_persona = next((p for p in active_personas if p.slug == slug), None)
        if match_persona is None:
            return None
        if match_persona.id not in seen:
            personas.append(match_persona)
            seen.add(match_persona.id)
        pos += match.end()
    if not personas:
        return None
    rest = text[pos:].strip()
    if not rest:
        return None
    return personas, rest


def parse_slash_command(
    message: str, active_personas: list[PersonaLike]
) -> tuple[PersonaLike, str] | None:
    """Kompatybilność: pojedynczy `/slug treść` → pierwsza persona z multi-parsera."""
    multi = parse_multi_slash_command(message, active_personas)
    if multi is None or len(multi[0]) != 1:
        return None
    return multi[0][0], multi[1]


def _normalize_persona_ids(raw_ids: list[str], allowlist: list[str]) -> list[str]:
    allow = set(allowlist)
    out: list[str] = []
    seen: set[str] = set()
    for persona_id in raw_ids:
        if persona_id in allow and persona_id not in seen:
            out.append(persona_id)
            seen.add(persona_id)
    return out


class ChatRoutingService:
    """Deprecated — produkcja to tura Goata + slash, nie `plan_consultation` (ADR-17).

    Zachowany dla testów regresji ADR-13; nie wołany z orchestratora.
    """

    def __init__(
        self,
        llm_client: RoutingLLMClientProtocol,
        chat_repo: RoutingRepositoryProtocol,
        *,
        chat_model: str,
    ) -> None:
        warnings.warn(
            "ChatRoutingService jest deprecated — produkcja: tura Goata + slash (ADR-17).",
            DeprecationWarning,
            stacklevel=2,
        )
        self._llm_client = llm_client
        self._chat_repo = chat_repo
        self._chat_model = chat_model

    async def route(
        self, *, session_id: str, message: str, active_personas: list[PersonaLike]
    ) -> RoutingResult:
        warnings.warn(
            "ChatRoutingService.route() jest deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
        if not active_personas:
            raise ValueError("route() wymaga co najmniej jednej aktywnej persony.")

        slash_match = parse_multi_slash_command(message, active_personas)
        if slash_match is not None:
            personas, rest = slash_match
            invoked: Literal["slash_command", "multi_slash"] = (
                "multi_slash" if len(personas) > 1 else "slash_command"
            )
            return RoutingResult(
                persona_ids=[p.id for p in personas],
                invoked_via=invoked,
                content=rest,
            )

        persona_ids = await self._classify(
            session_id=session_id, message=message, active_personas=active_personas
        )
        return RoutingResult(persona_ids=persona_ids, invoked_via="auto_routed", content=message)

    async def _classify(
        self, *, session_id: str, message: str, active_personas: list[PersonaLike]
    ) -> list[str]:
        ids = [persona.id for persona in active_personas]

        if len(active_personas) == 1:
            return [ids[0]]

        max_n = len(ids)
        descriptions = "\n".join(
            routing_persona_line(
                persona_id=persona.id,
                persona_type=persona.type,
                first_sentence=_first_sentence(persona.system_prompt),
            )
            for persona in active_personas
        )
        system_message = (
            "Wybierz od 1 do "
            f"{max_n} person (po polu id), które powinny ODPOWIEDZIEĆ SEKWENCYJNIE na "
            "wiadomość użytkownika. Kolejność listy = kolejność odpowiedzi.\n\n"
            f"{ROUTING_CLASSIFIER_RULES}\n\n"
            "Dostępne persony:\n"
            + descriptions
        )
        json_schema = {
            "name": _ROUTING_JSON_SCHEMA_NAME,
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "persona_ids": {
                        "type": "array",
                        "items": {"type": "string", "enum": ids},
                        "minItems": 1,
                        "maxItems": max_n,
                        "uniqueItems": True,
                    }
                },
                "required": ["persona_ids"],
                "additionalProperties": False,
            },
        }

        try:
            result = await self._llm_client.complete_json(
                model=self._chat_model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": message},
                ],
                json_schema=json_schema,
                max_tokens=120,
            )
            raw_list = result.get("persona_ids")
            if not isinstance(raw_list, list):
                # Legacy single-id response
                legacy = result.get("persona_id")
                raw_list = [legacy] if isinstance(legacy, str) else []
            normalized = _normalize_persona_ids(
                [str(x) for x in raw_list],
                ids,
            )
            if normalized:
                return normalized
            logger.warning("routing_classifier_invalid_ids", returned=raw_list)
        except Exception as exc:  # noqa: BLE001 — fallback poniżej
            logger.warning("routing_classifier_failed", error=str(exc))

        fallback = await self._chat_repo.get_last_responding_persona(session_id)
        if fallback is not None and fallback in ids:
            return [fallback]
        return [ids[0]]
