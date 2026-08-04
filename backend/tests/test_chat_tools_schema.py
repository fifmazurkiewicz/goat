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


def test_get_team_lead_plan_tools_only_get_and_rebuild() -> None:
    names = {t["function"]["name"] for t in get_team_lead_plan_tools()}
    assert names == {"get_plan", "rebuild_plan"}


def test_trainer_and_team_lead_tool_sets_disjoint_except_get_plan() -> None:
    trainer = {t["function"]["name"] for t in get_trainer_chat_tools()}
    goat = {t["function"]["name"] for t in get_team_lead_plan_tools()}
    assert trainer & goat == {"get_plan"}
    assert "rebuild_plan" in goat and "rebuild_plan" not in trainer
