"""Testy jednostkowe Goata w orchestratorze (persistencja, etykiety)."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.chat.orchestrator import _persist_persona_id
from app.domain.chat.team_lead import (
    TEAM_LEAD_DISPLAY_LABEL,
    TeamLeadSpeaker,
    persona_display_label,
)


@dataclass
class _FakePersona:
    id: str
    type: str
    name: str
    slug: str = "trener"
    system_prompt: str = "Jestem trenerem."


def test_persist_persona_id_none_for_team_lead() -> None:
    assert _persist_persona_id(TeamLeadSpeaker()) is None


def test_persist_persona_id_returns_uuid_for_trainer() -> None:
    p = _FakePersona(id="abc-123", type="dietitian", name="Anna")
    assert _persist_persona_id(p) == "abc-123"


def test_persona_display_label_formats_name_and_role() -> None:
    p = _FakePersona(id="x", type="dietitian", name="Anna")
    assert persona_display_label(p) == "Anna · Dietetyk"


def test_team_lead_speaker_constants() -> None:
    goat = TeamLeadSpeaker()
    assert goat.type == "team_lead"
    assert goat.name == "Goat"
    assert TEAM_LEAD_DISPLAY_LABEL == "Goat · Kierownik Zespołu"
