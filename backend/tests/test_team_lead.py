"""Testy Kierownika Zespołu — plan konsultacji bez LLM (slash)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.domain.chat.team_lead import (
    TeamLeadService,
    build_consultation_user_message,
    build_plan_only_consultation,
    is_plan_coordination_only,
    user_requests_plan_rebuild,
)


def test_user_requests_plan_rebuild_detects_harmonized_plan() -> None:
    assert user_requests_plan_rebuild("Generuj zharmonizowany plan na sierpień")


def test_is_plan_coordination_only_without_detail_questions() -> None:
    assert is_plan_coordination_only("Ułóż plan na sierpień w Plany")


def test_is_plan_coordination_only_false_when_diet_question() -> None:
    assert not is_plan_coordination_only("Ułóż plan na tydzień i powiedz co jeść na śniadanie")


def test_user_requests_plan_rebuild_negative_cases() -> None:
    assert not user_requests_plan_rebuild("Jaka jest harmonia w muzyce?")
    assert not user_requests_plan_rebuild("Opowiedz o planie marketingowym firmy")
    assert not user_requests_plan_rebuild("Cześć, jak się masz?")


def test_build_plan_only_consultation_skips_llm_for_harmonized_plan() -> None:
    personas = [
        _FakePersona(id="a", type="dietitian", slug="dietetyk"),
        _FakePersona(id="b", type="personal_trainer", slug="trener"),
    ]
    plan = build_plan_only_consultation(
        message="Generuj zharmonizowany plan na sierpień", active_personas=personas
    )
    assert plan is not None
    assert plan.status_message.startswith("Goat")
    assert plan.persona_ids == ["a"]


def test_build_plan_only_consultation_none_when_diet_question() -> None:
    personas = [_FakePersona(id="a", type="dietitian", slug="dietetyk")]
    assert (
        build_plan_only_consultation(
            message="Ułóż plan na tydzień i powiedz co jeść", active_personas=personas
        )
        is None
    )


def test_build_plan_only_consultation_respects_slash() -> None:
    personas = [
        _FakePersona(id="a", type="dietitian", slug="dietetyk"),
        _FakePersona(id="b", type="personal_trainer", slug="trener"),
    ]
    plan = build_plan_only_consultation(
        message="/dietetyk ułóż plan na tydzień", active_personas=personas
    )
    assert plan is not None
    assert plan.invoked_via == "slash_command"
    assert plan.persona_ids == ["a"]
    assert plan.content == "ułóż plan na tydzień"


def test_persona_display_label_for_trainer() -> None:
    from app.domain.chat.team_lead import persona_display_label

    p = _FakePersona(id="b", type="personal_trainer", slug="trener", name="Kasia")
    assert persona_display_label(p) == "Kasia · Trener personalny"


@pytest.mark.asyncio
async def test_team_lead_fallback_uses_last_responding_persona():
    personas = [
        _FakePersona(id="a", type="dietitian", slug="dietetyk"),
        _FakePersona(id="b", type="personal_trainer", slug="trener"),
    ]

    class _Repo:
        async def get_last_responding_persona(self, session_id: str) -> str | None:
            assert session_id == "sess-1"
            return "b"

    service = TeamLeadService(_FakeLLM(), chat_model="test", chat_repo=_Repo())
    plan = await service.plan_consultation(
        message="Co jem na kolację?",
        active_personas=personas,
        session_id="sess-1",
    )
    assert plan.persona_ids == ["b"]


@pytest.mark.asyncio
async def test_plan_consultation_single_persona_skips_llm():
    p = _FakePersona(id="only", type="dietitian", slug="dietetyk")
    service = TeamLeadService(_FakeLLMNoCall(), chat_model="test")
    plan = await service.plan_consultation(message="Co jem na śniadanie?", active_personas=[p])
    assert plan.persona_ids == ["only"]
    assert plan.invoked_via == "auto_routed"
    assert "dietetyk" in plan.status_message.lower() or "only" in plan.status_message.lower()


@dataclass
class _FakePersona:
    id: str
    type: str
    slug: str
    name: str = "Trener"
    system_prompt: str = "Jestem trenerem."


class _FakeLLM:
    async def complete_json(self, **kwargs):  # noqa: ANN003
        raise RuntimeError("LLM unavailable")


class _FakeLLMNoCall:
    async def complete_json(self, **kwargs):  # noqa: ANN003
        raise AssertionError("LLM nie powinien być wołany przy slash")


@pytest.mark.asyncio
async def test_team_lead_respects_multi_slash():
    personas = [
        _FakePersona(id="a", type="dietitian", slug="dietetyk"),
        _FakePersona(id="b", type="personal_trainer", slug="trener"),
    ]
    service = TeamLeadService(_FakeLLMNoCall(), chat_model="test")
    plan = await service.plan_consultation(
        message="/dietetyk /trener ułóż plan na tydzień", active_personas=personas
    )
    assert plan.persona_ids == ["a", "b"]
    assert plan.content == "ułóż plan na tydzień"
    assert plan.invoked_via == "multi_slash"


def test_build_consultation_user_message_includes_prior():
    msg = build_consultation_user_message(
        user_content="Co jem na śniadanie?",
        team_brief="Skoordynuj dietę.",
        persona_brief="Zaproponuj makro.",
        prior_summaries=[("Trener", "Dziś trening siłowy.")],
    )
    assert "Co jem na śniadanie?" in msg
    assert "[BRIEF KIEROWNIKA ZESPOŁU]" in msg
    assert "Trener" in msg
