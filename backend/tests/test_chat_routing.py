"""Testy `ChatRoutingService` — parsowanie `/slug` (deterministyczne) + fallback
klasyfikatora LLM (ADR-13, architecture.md §3a)."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.chat.routing import ChatRoutingService, parse_slash_command


@dataclass(frozen=True, slots=True)
class _Persona:
    id: str
    type: str
    slug: str
    system_prompt: str


_TRAINER = _Persona(id="p-trainer", type="personal_trainer", slug="trener", system_prompt="Jesteś trenerem.")
_DIETITIAN = _Persona(id="p-diet", type="dietitian", slug="dietetyk", system_prompt="Jesteś dietetykiem.")


class _FakeLLMClient:
    def __init__(self, response: dict | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error

    async def complete_json(self, **kwargs: object) -> dict:
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


class _FakeChatRepo:
    def __init__(self, last_responding_persona: str | None = None) -> None:
        self._last = last_responding_persona

    async def get_last_responding_persona(self, session_id: str) -> str | None:
        return self._last


def test_parse_slash_command_matches_active_persona() -> None:
    result = parse_slash_command("/trener jak zrobić przysiad?", [_TRAINER, _DIETITIAN])

    assert result is not None
    persona, rest = result
    assert persona.id == _TRAINER.id
    assert rest == "jak zrobić przysiad?"


def test_parse_slash_command_unknown_slug_returns_none() -> None:
    assert parse_slash_command("/nieznany cześć", [_TRAINER]) is None


def test_parse_slash_command_no_prefix_returns_none() -> None:
    assert parse_slash_command("zwykła wiadomość", [_TRAINER]) is None


async def test_route_uses_slash_command_without_calling_llm() -> None:
    service = ChatRoutingService(_FakeLLMClient(error=RuntimeError("nie powinno być wołane")),
                                  _FakeChatRepo(), chat_model="test-model")

    result = await service.route(
        session_id="s1", message="/dietetyk co jeść przed treningiem?", active_personas=[_TRAINER, _DIETITIAN]
    )

    assert result.persona_id == _DIETITIAN.id
    assert result.invoked_via == "slash_command"
    assert result.content == "co jeść przed treningiem?"


async def test_route_single_active_persona_skips_classifier() -> None:
    service = ChatRoutingService(_FakeLLMClient(error=RuntimeError("nie powinno być wołane")),
                                  _FakeChatRepo(), chat_model="test-model")

    result = await service.route(session_id="s1", message="cześć", active_personas=[_TRAINER])

    assert result.persona_id == _TRAINER.id
    assert result.invoked_via == "auto_routed"


async def test_route_classifier_selects_persona() -> None:
    service = ChatRoutingService(
        _FakeLLMClient(response={"persona_id": _DIETITIAN.id}),
        _FakeChatRepo(),
        chat_model="test-model",
    )

    result = await service.route(
        session_id="s1", message="co jeść przed meczem?", active_personas=[_TRAINER, _DIETITIAN]
    )

    assert result.persona_id == _DIETITIAN.id
    assert result.invoked_via == "auto_routed"


async def test_route_classifier_failure_falls_back_to_last_responding_persona() -> None:
    service = ChatRoutingService(
        _FakeLLMClient(error=RuntimeError("openrouter down")),
        _FakeChatRepo(last_responding_persona=_DIETITIAN.id),
        chat_model="test-model",
    )

    result = await service.route(
        session_id="s1", message="a co teraz?", active_personas=[_TRAINER, _DIETITIAN]
    )

    assert result.persona_id == _DIETITIAN.id


async def test_route_classifier_invalid_id_falls_back_to_first_persona() -> None:
    service = ChatRoutingService(
        _FakeLLMClient(response={"persona_id": "not-a-real-id"}),
        _FakeChatRepo(last_responding_persona=None),
        chat_model="test-model",
    )

    result = await service.route(
        session_id="s1", message="hej", active_personas=[_TRAINER, _DIETITIAN]
    )

    assert result.persona_id == _TRAINER.id
