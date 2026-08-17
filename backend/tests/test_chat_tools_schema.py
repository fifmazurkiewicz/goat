"""Rejestr tooli czatu — log_result, profil, plany, podział trener vs Goat."""

from __future__ import annotations

from app.domain.chat.tools import (
    get_chat_tools,
    get_team_lead_plan_tools,
    get_trainer_chat_tools,
)


def test_get_chat_tools_includes_plan_tools() -> None:
    names = {t["function"]["name"] for t in get_chat_tools()}
    assert names == {
        "log_result",
        "update_user_profile",
        "get_plan",
        "upsert_plan_items",
        "rebuild_plan",
    }


def test_get_trainer_chat_tools_excludes_rebuild_plan() -> None:
    names = {t["function"]["name"] for t in get_trainer_chat_tools()}
    assert "rebuild_plan" not in names
    assert names == {
        "log_result",
        "update_user_profile",
        "get_plan",
        "upsert_plan_items",
    }


def test_get_team_lead_plan_tools_includes_consult_persona() -> None:
    names = {t["function"]["name"] for t in get_team_lead_plan_tools()}
    assert names == {
        "get_plan",
        "rebuild_plan",
        "update_user_profile",
        "consult_persona",
        "upsert_plan_items",
        "log_result",
    }


def test_team_lead_can_log_results() -> None:
    """Goat zapisuje wyniki zaraportowane w sesji `general` (spec 2026-08-17)."""
    names = {t["function"]["name"] for t in get_team_lead_plan_tools()}
    assert "log_result" in names


def test_trainer_tools_exclude_consult_persona() -> None:
    names = {t["function"]["name"] for t in get_trainer_chat_tools()}
    assert "consult_persona" not in names


def test_consult_persona_schema_requires_slug_and_question() -> None:
    from app.domain.chat.tools import CONSULT_PERSONA_TOOL_SCHEMA

    fn = CONSULT_PERSONA_TOOL_SCHEMA["function"]
    assert fn["name"] == "consult_persona"
    params = fn["parameters"]
    assert set(params["required"]) == {"slug", "question"}
    assert params["additionalProperties"] is False
    assert "rzadko" in fn["description"].lower() or "tylko gdy" in fn["description"].lower()


def test_rebuild_plan_schema_accepts_optional_user_brief() -> None:
    from app.domain.chat.tools import REBUILD_PLAN_TOOL_SCHEMA

    fn = REBUILD_PLAN_TOOL_SCHEMA["function"]
    props = fn["parameters"]["properties"]
    assert "user_brief" in props
    assert set(fn["parameters"]["required"]) == {"period_type", "start_date"}


def test_trainer_and_team_lead_tool_sets_disjoint_except_shared() -> None:
    trainer = {t["function"]["name"] for t in get_trainer_chat_tools()}
    goat = {t["function"]["name"] for t in get_team_lead_plan_tools()}
    assert trainer & goat == {
        "get_plan",
        "update_user_profile",
        "upsert_plan_items",
        "log_result",
    }
    assert "rebuild_plan" in goat and "rebuild_plan" not in trainer
    assert "consult_persona" in goat and "consult_persona" not in trainer
