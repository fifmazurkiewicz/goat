"""Testy jednostkowe Goata w orchestratorze (persistencja, etykiety, zapis wyników)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from app.domain.chat.orchestrator import (
    ChatOrchestrator,
    _persist_persona_id,
    _result_source_persona_id,
)
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


# ============ log_result u Goata (spec 2026-08-17) ============


def test_result_source_persona_id_is_none_for_team_lead() -> None:
    """`__team_lead__` nie jest UUID — FK `results.source_persona_id` wymaga NULL."""
    assert _result_source_persona_id(TeamLeadSpeaker()) is None


def test_result_source_persona_id_is_uuid_for_trainer() -> None:
    p = _FakePersona(id="abc-123", type="motor_coach", name="Bartek")
    assert _result_source_persona_id(p) == "abc-123"


class _SpyResultsService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def log_batch_from_agent(
        self, *, user_id: str, source_persona_id: str | None, entries: list[dict[str, Any]]
    ) -> list[Any]:
        self.calls.append(
            {"user_id": user_id, "source_persona_id": source_persona_id, "entries": entries}
        )

        @dataclass
        class _Outcome:
            index: int
            ok: bool
            error: str | None = None

        return [_Outcome(i, True) for i, _ in enumerate(entries)]


_LOG_ARGS = json.dumps(
    {
        "entries": [
            {"category": "strength", "metric": "bench_press_kg", "value": 45, "date": "2026-08-17"}
        ]
    }
)


@pytest.mark.asyncio
async def test_team_lead_log_result_persists_with_null_source_persona() -> None:
    """GWT-5: Goat zapisuje zaraportowany wynik; `source_persona_id=NULL`."""
    orchestrator = ChatOrchestrator.__new__(ChatOrchestrator)
    spy = _SpyResultsService()

    response = await orchestrator._run_single_tool(
        name="log_result",
        raw_arguments=_LOG_ARGS,
        user_id="u1",
        persona=TeamLeadSpeaker(),
        results_service=spy,  # type: ignore[arg-type]
        user_profile_repo=object(),  # type: ignore[arg-type]
        plan_tools=object(),  # type: ignore[arg-type]
    )

    assert spy.calls, "Goat musi móc zapisać wynik (log_result nie może być odrzucone)"
    assert spy.calls[0]["source_persona_id"] is None
    assert '"status": "ok"' in response or '"status":"ok"' in response


@pytest.mark.asyncio
async def test_trainer_log_result_keeps_persona_uuid() -> None:
    """GWT-6: brak regresji — trener zapisuje z własnym UUID."""
    orchestrator = ChatOrchestrator.__new__(ChatOrchestrator)
    spy = _SpyResultsService()

    await orchestrator._run_single_tool(
        name="log_result",
        raw_arguments=_LOG_ARGS,
        user_id="u1",
        persona=_FakePersona(id="uuid-trainer", type="motor_coach", name="Bartek"),
        results_service=spy,  # type: ignore[arg-type]
        user_profile_repo=object(),  # type: ignore[arg-type]
        plan_tools=object(),  # type: ignore[arg-type]
    )

    assert spy.calls[0]["source_persona_id"] == "uuid-trainer"
