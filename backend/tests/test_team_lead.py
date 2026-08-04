"""Testy Kierownika Zespołu — plan konsultacji bez LLM (slash)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.domain.chat.team_lead import TeamLeadService, build_consultation_user_message


@dataclass
class _FakePersona:
    id: str
    type: str
    slug: str
    system_prompt: str = "Jestem trenerem."


class _FakeLLM:
    async def complete_json(self, **kwargs):  # noqa: ANN003
        raise AssertionError("LLM nie powinien być wołany przy slash")


@pytest.mark.asyncio
async def test_team_lead_respects_multi_slash():
    personas = [
        _FakePersona(id="a", type="dietitian", slug="dietetyk"),
        _FakePersona(id="b", type="personal_trainer", slug="trener"),
    ]
    service = TeamLeadService(_FakeLLM(), chat_model="test")
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
