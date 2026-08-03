"""`ChatRoutingService` — wybór DOKŁADNIE JEDNEJ persony odpowiadającej w sesji `general`
(ADR-13, architecture.md sekcja 3a, ai-pipeline.md sekcja 1a).

Kolejność: (1) deterministyczne parsowanie `/slug` (zero LLM), (2) tanie wywołanie
klasyfikujące `chat_model` z `response_format: json_schema` ograniczonym do aktywnych
person, (3) fallback — ostatnia odpowiadająca persona w sesji, albo pierwsza aktywna.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol

import structlog

logger = structlog.get_logger(__name__)

_SLASH_COMMAND_RE = re.compile(r"^/([a-z0-9_]+)\s+(.+)", re.DOTALL)


class PersonaLike(Protocol):
    id: str
    type: str
    slug: str
    system_prompt: str


@dataclass(frozen=True, slots=True)
class RoutingResult:
    persona_id: str
    invoked_via: Literal["slash_command", "auto_routed"]
    content: str  # treść wiadomości (bez prefiksu `/slug` gdy dotyczy)


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


def parse_slash_command(
    message: str, active_personas: list[PersonaLike]
) -> tuple[PersonaLike, str] | None:
    """Parsowanie `/slug treść` — deterministyczne, zero LLM (architecture.md §3a pkt 1).
    Lookup wyłącznie wśród AKTYWNYCH person usera. `None` gdy brak prefiksu `/` albo
    slug nie pasuje do żadnej aktywnej persony (wtedy traktujemy jako zwykłą wiadomość,
    routing klasyfikatorem przejmuje kontrolę)."""
    match = _SLASH_COMMAND_RE.match(message.strip())
    if match is None:
        return None
    slug, rest = match.group(1), match.group(2)
    for persona in active_personas:
        if persona.slug == slug:
            return persona, rest
    return None


class ChatRoutingService:
    """Nie zna FastAPI/HTTP — testowalna z fake LLM client + repo (architecture.md §7)."""

    def __init__(
        self,
        llm_client: RoutingLLMClientProtocol,
        chat_repo: RoutingRepositoryProtocol,
        *,
        chat_model: str,
    ) -> None:
        self._llm_client = llm_client
        self._chat_repo = chat_repo
        self._chat_model = chat_model

    async def route(
        self, *, session_id: str, message: str, active_personas: list[PersonaLike]
    ) -> RoutingResult:
        if not active_personas:
            raise ValueError("route() wymaga co najmniej jednej aktywnej persony.")

        slash_match = parse_slash_command(message, active_personas)
        if slash_match is not None:
            persona, rest = slash_match
            return RoutingResult(persona_id=persona.id, invoked_via="slash_command", content=rest)

        persona_id = await self._classify(
            session_id=session_id, message=message, active_personas=active_personas
        )
        return RoutingResult(persona_id=persona_id, invoked_via="auto_routed", content=message)

    async def _classify(
        self, *, session_id: str, message: str, active_personas: list[PersonaLike]
    ) -> str:
        ids = [persona.id for persona in active_personas]

        if len(active_personas) == 1:
            return ids[0]

        descriptions = "\n".join(
            f"- id={persona.id} | typ={persona.type} | {_first_sentence(persona.system_prompt)}"
            for persona in active_personas
        )
        system_message = (
            "Wybierz DOKŁADNIE jedną personę (po polu id), która najlepiej odpowie na "
            "wiadomość użytkownika w kontekście coachingu sportowego/dietetycznego/"
            "psychologicznego. Dostępne persony:\n" + descriptions
        )
        json_schema = {
            "name": _ROUTING_JSON_SCHEMA_NAME,
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"persona_id": {"type": "string", "enum": ids}},
                "required": ["persona_id"],
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
                max_tokens=50,
            )
            persona_id = result.get("persona_id")
            if persona_id in ids:
                return persona_id  # type: ignore[return-value]
            logger.warning("routing_classifier_invalid_id", returned=persona_id)
        except Exception as exc:  # noqa: BLE001 — fallback poniżej, nie eskalujemy
            logger.warning("routing_classifier_failed", error=str(exc))

        fallback = await self._chat_repo.get_last_responding_persona(session_id)
        if fallback is not None and fallback in ids:
            return fallback
        return ids[0]
