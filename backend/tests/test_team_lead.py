"""Testy Kierownika Zespołu — heurystyki i helpery tury Goata."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.chat.team_lead import (
    MAX_CONSULTS_PER_TURN,
    build_goat_turn_prompt,
    consult_scope_hint,
    goat_consult_status_message,
    is_direct_persona_invocation,
    is_plan_coordination_only,
    persona_display_label,
    resolve_persona_by_slug,
    user_requests_all_trainers,
    user_requests_plan_rebuild,
)


def test_max_consults_is_five() -> None:
    assert MAX_CONSULTS_PER_TURN == 5


def test_resolve_persona_by_slug_finds_motor_coach() -> None:
    diet = _FakePersona(id="a", type="dietitian", slug="dietetyk", name="Anna")
    motor = _FakePersona(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    assert resolve_persona_by_slug("motoryka", [diet, motor]) is motor
    assert resolve_persona_by_slug("nie-ma", [diet, motor]) is None


def test_goat_consult_status_message_copy() -> None:
    p = _FakePersona(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    assert goat_consult_status_message(p) == "Goat konsultuje z Bartek · Trener motoryczny…"


def test_consult_scope_hint_motor_not_dietitian() -> None:
    diet = _FakePersona(id="a", type="dietitian", slug="dietetyk", name="Anna")
    motor = _FakePersona(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    hint = consult_scope_hint(
        message="Jak poprawić plyometrię i skok?",
        active_personas=[diet, motor],
    )
    assert hint is not None
    assert "motoryka" in hint
    assert "dietetyk" not in hint


def test_consult_scope_hint_matches_custom_persona_from_prompt() -> None:
    diet = _FakePersona(id="a", type="dietitian", slug="dietetyk", name="Anna")
    swim = _FakePersona(
        id="c",
        type="custom",
        slug="plywanie",
        name="Ola",
        system_prompt="Jestem trenerką pływania: technika kraula, nawroty, trening w wodzie.",
    )
    hint = consult_scope_hint(
        message="Jak poprawić technikę kraula?",
        active_personas=[diet, swim],
    )
    assert hint is not None
    assert "plywanie" in hint
    assert "dietetyk" not in hint


def test_consult_scope_hint_none_when_no_roster_match() -> None:
    diet = _FakePersona(id="a", type="dietitian", slug="dietetyk", name="Anna")
    assert (
        consult_scope_hint(message="Jak poprawić plyometrię?", active_personas=[diet]) is None
    )


def test_build_goat_turn_prompt_includes_roster_and_consult_tool() -> None:
    diet = _FakePersona(id="a", type="dietitian", slug="dietetyk", name="Anna")
    motor = _FakePersona(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    prompt = build_goat_turn_prompt(
        active_personas=[diet, motor],
        user_message="Jak trenować motorykę?",
    )
    assert "consult_persona" in prompt
    assert "motoryka" in prompt
    assert "dietetyk" in prompt
    assert "plyometria" in prompt.lower() or "motor_coach" in prompt


def test_user_requests_plan_rebuild_detects_harmonized_plan() -> None:
    assert user_requests_plan_rebuild("Generuj zharmonizowany plan na sierpień")


def test_user_requests_plan_rebuild_detects_update_and_complaints() -> None:
    assert user_requests_plan_rebuild("Zaktualizuj plan na ten tydzień")
    assert user_requests_plan_rebuild(
        "W aktualnym planie widzę w każdy dzień trening badmintonowy"
    )
    assert user_requests_plan_rebuild("Przebuduj plan bez badmintona")


def test_is_plan_coordination_only_without_detail_questions() -> None:
    assert is_plan_coordination_only("Ułóż plan na sierpień w Plany")
    assert is_plan_coordination_only("Zaktualizuj plan na ten tydzień — bez badmintona")


def test_is_plan_coordination_only_false_when_diet_question() -> None:
    assert not is_plan_coordination_only("Ułóż plan na tydzień i powiedz co jeść na śniadanie")


def test_user_requests_plan_rebuild_negative_cases() -> None:
    assert not user_requests_plan_rebuild("Jaka jest harmonia w muzyce?")
    assert not user_requests_plan_rebuild("Opowiedz o planie marketingowym firmy")
    assert not user_requests_plan_rebuild("Cześć, jak się masz?")


def test_build_goat_turn_prompt_prefers_no_consult_on_simple_greeting() -> None:
    diet = _FakePersona(id="a", type="dietitian", slug="dietetyk", name="Anna")
    prompt = build_goat_turn_prompt(active_personas=[diet], user_message="Cześć")
    assert "NIE wołaj consult_persona" in prompt or "bez consult_persona" in prompt.lower()
    assert "proste" in prompt.lower() or "samodzielnie" in prompt.lower()


def test_build_goat_turn_prompt_plan_only_forbids_consult() -> None:
    motor = _FakePersona(id="b", type="motor_coach", slug="motoryka", name="Bartek")
    prompt = build_goat_turn_prompt(
        active_personas=[motor],
        user_message="Zaktualizuj plan na ten tydzień — bez badmintona",
    )
    assert "rebuild_plan" in prompt
    assert "NIE wołaj consult_persona" in prompt


def test_plan_brief_excludes_badminton_coach() -> None:
    from app.domain.chat.team_lead import plan_brief_excludes_persona_type

    brief = "Tydzień bez badmintona — tylko siłownia i bieganie"
    assert plan_brief_excludes_persona_type(brief, "badminton_coach")
    assert not plan_brief_excludes_persona_type(brief, "motor_coach")
    assert not plan_brief_excludes_persona_type("Więcej badmintona na hali", "badminton_coach")


def test_persona_display_label_for_trainer() -> None:
    p = _FakePersona(id="b", type="personal_trainer", slug="trener", name="Kasia")
    assert persona_display_label(p) == "Kasia · Trener personalny"


def test_persona_display_label_dedupes_when_name_equals_role() -> None:
    p = _FakePersona(id="a", type="dietitian", slug="dietetyk", name="Dietetyk")
    assert persona_display_label(p) == "Dietetyk"


def test_is_direct_persona_invocation_only_for_slash() -> None:
    assert is_direct_persona_invocation("slash_command")
    assert is_direct_persona_invocation("multi_slash")
    assert not is_direct_persona_invocation("auto_routed")
    assert not is_direct_persona_invocation(None)


def test_user_requests_all_trainers_detects_roundtable() -> None:
    assert user_requests_all_trainers("Niech każdy napisze coś od siebie")
    assert user_requests_all_trainers("Z jakich trenerów składa się nasz zespół?")
    assert user_requests_all_trainers(
        "Co wiesz o mnie? Z jakich person składa się nasz zespół? Niech każdy powie coś od siebie"
    )
    assert user_requests_all_trainers("Niech każdy powie coś od siebie")


def test_user_requests_all_trainers_negative() -> None:
    assert not user_requests_all_trainers("Co jem na śniadanie?")


@dataclass
class _FakePersona:
    id: str
    type: str
    slug: str
    name: str = "Trener"
    system_prompt: str = "Jestem trenerem."
