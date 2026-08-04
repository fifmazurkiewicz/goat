"""Rejestr tooli czatu — log_result, profil, plany."""

from __future__ import annotations

from app.domain.chat.tools import get_chat_tools


def test_get_chat_tools_includes_plan_tools() -> None:
    names = {t["function"]["name"] for t in get_chat_tools()}
    assert names == {
        "log_result",
        "update_user_profile",
        "get_plan",
        "upsert_plan_items",
        "rebuild_plan",
    }
