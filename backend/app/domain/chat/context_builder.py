"""`ContextBuilder` — assembles system prompt + message history into the OpenRouter API format.

See docs/technical/architecture.md section 5 (chat context, token budget) and section 3a
(history filtering per-persona in a `general` session), docs/technical/ai-pipeline.md
section 0 (user profile) and section 3 (token budget).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from app.domain.chat.preamble import build_system_prompt as build_preamble_composed
from app.domain.chat.tools import build_profile_intake_instruction
from app.models.schemas import UserProfileOut

# App is PL — relative dates ("yesterday") are counted in the user's timezone, not server UTC.
_APP_TZ = ZoneInfo("Europe/Warsaw")

_WEEKDAY_PL = (
    "poniedziałek",
    "wtorek",
    "środa",
    "czwartek",
    "piątek",
    "sobota",
    "niedziela",
)


class ChatRepositoryProtocol(Protocol):
    async def list_recent_messages_for_context(
        self, *, session_id: str, persona_id: str | None, session_type: str, limit: int
    ) -> list[Any]: ...


_ACTIVITY_LABELS = {
    "sedentary": "siedzący",
    "light": "lekko aktywny",
    "moderate": "umiarkowanie aktywny",
    "active": "aktywny",
    "very_active": "bardzo aktywny",
}
_GOAL_LABELS = {
    "lose_weight": "redukcja masy ciała",
    "build_muscle": "budowa masy mięśniowej",
    "improve_endurance": "poprawa wydolności",
    "general_health": "ogólne zdrowie",
    "sport_specific": "cel specyficzny dla sportu",
}


def _today_warsaw() -> date:
    return datetime.now(_APP_TZ).date()


def _age_years(date_of_birth: date | None) -> int | None:
    if date_of_birth is None:
        return None
    today = _today_warsaw()
    years = today.year - date_of_birth.year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        years -= 1
    return years


def build_temporal_context_block(*, today: date | None = None) -> str:
    """Today's date (Europe/Warsaw) — the model doesn't know the calendar from training;
    without this "yesterday" / ISO `date` in `log_result` is guessed."""
    day = today or _today_warsaw()
    weekday = _WEEKDAY_PL[day.weekday()]
    return (
        "[KONTEKST CZASOWY]\n"
        f"Dzisiaj jest {weekday}, {day.isoformat()} (strefa Europe/Warsaw). "
        "Względne daty usera („wczoraj”, „w poniedziałek”) przeliczaj na ISO YYYY-MM-DD "
        "względem tej daty. Przy log_result pole date MUSI być konkretną datą ISO, "
        "nigdy słowem „wczoraj”."
    )


def build_user_profile_block(profile: UserProfileOut | None) -> str | None:
    """Deterministic block (no LLM) appended to EVERY message (architecture.md §5) —
    `None` when there's no data at all (instead of an empty section in the prompt)."""
    if profile is None:
        return None

    parts: list[str] = []
    if profile.height_cm is not None:
        parts.append(f"wzrost: {profile.height_cm:g} cm")
    if profile.weight_kg is not None:
        parts.append(f"waga: {profile.weight_kg:g} kg")
    age = _age_years(profile.date_of_birth)
    if age is not None:
        parts.append(f"wiek: {age} lat")
    if profile.sex:
        parts.append(f"płeć: {profile.sex}")
    if profile.activity_level:
        parts.append(f"poziom aktywności: {_ACTIVITY_LABELS.get(profile.activity_level, profile.activity_level)}")
    if profile.primary_goal:
        parts.append(f"główny cel: {_GOAL_LABELS.get(profile.primary_goal, profile.primary_goal)}")
    if profile.notes:
        parts.append(f"notatki: {profile.notes}")

    if not parts:
        return None
    return "[PROFIL UŻYTKOWNIKA]\n" + ", ".join(parts)


def build_recent_results_block(results: list[Any]) -> str | None:
    """Summary of recent results — the persona has memory of what the user reported."""
    if not results:
        return None
    lines: list[str] = []
    for row in results[:12]:
        logged = getattr(row, "logged_date", None)
        date_str = logged.isoformat() if logged is not None else "?"
        category = getattr(row, "category", "")
        metric = getattr(row, "metric", "")
        value = getattr(row, "value", "")
        unit = getattr(row, "unit", "") or ""
        lines.append(f"- {date_str} | {category}/{metric}: {value}{unit}")
    return "[OSTATNIE WYNIKI UŻYTKOWNIKA]\n" + "\n".join(lines)


def build_plan_summary_block(plan: Any | None, items: list[Any]) -> str | None:
    """Active plan in the calendar — summary of items for the coming days."""
    if plan is None:
        return "[PLAN TRENINGOWY]\nNo active plan in the calendar."
    header = (
        f"Plan {plan.period_type} {plan.start_date.isoformat()}–{plan.end_date.isoformat()} "
        f"(status: {plan.status})"
    )
    if not items:
        return f"[PLAN TRENINGOWY]\n{header}\nNo items — you can suggest rebuild_plan."
    lines = [header, "Upcoming items:"]
    for item in items[:14]:
        content = item.content if isinstance(getattr(item, "content", None), dict) else {}
        title = content.get("title") or item.item_type
        lines.append(f"- {item.item_date.isoformat()}: {title}")
    return "[PLAN TRENINGOWY]\n" + "\n".join(lines)


class ContextBuilder:
    """Doesn't know FastAPI/HTTP — testable with a fake `ChatRepositoryProtocol`."""

    def __init__(self, chat_repo: ChatRepositoryProtocol, *, history_window_messages: int) -> None:
        self._chat_repo = chat_repo
        self._history_window_messages = history_window_messages

    def build_system_prompt(
        self,
        *,
        persona_type: str,
        persona_system_prompt: str,
        persona_constraints: str | None,
        user_profile: UserProfileOut | None,
        template_safety_prompt: str | None = None,
        recent_results: list[Any] | None = None,
        plan_row: Any | None = None,
        plan_items: list[Any] | None = None,
    ) -> str:
        segments = [
            build_preamble_composed(
                persona_system_prompt,
                template_safety_prompt=template_safety_prompt,
                persona_type=persona_type,
            ),
            build_temporal_context_block(),
        ]

        if persona_constraints:
            segments.append(f"[TWARDE OGRANICZENIA PERSONY]\n{persona_constraints}")

        profile_block = build_user_profile_block(user_profile)
        if profile_block:
            segments.append(profile_block)

        results_block = build_recent_results_block(recent_results or [])
        if results_block:
            segments.append(results_block)

        plan_block = build_plan_summary_block(plan_row, plan_items or [])
        if plan_block:
            segments.append(plan_block)

        intake_instruction = build_profile_intake_instruction(user_profile)
        if intake_instruction:
            segments.append(intake_instruction)

        return "\n\n".join(segments)

    async def build_message_history(
        self, *, session_id: str, session_type: str, persona_id: str | None
    ) -> list[dict[str, Any]]:
        """Sliding window of the last M messages -> OpenAI/OpenRouter format (`role`,
        `content`, optionally `tool_calls`/`tool_call_id`) — without rolling summary (ADR-7)."""
        rows = await self._chat_repo.list_recent_messages_for_context(
            session_id=session_id,
            persona_id=persona_id,
            session_type=session_type,
            limit=self._history_window_messages,
        )
        return [_row_to_api_message(row) for row in rows]


def _row_to_api_message(row: Any) -> dict[str, Any]:
    if row.role == "tool":
        tool_call_id = (row.tool_calls or {}).get("tool_call_id")
        return {"role": "tool", "tool_call_id": tool_call_id, "content": row.content or ""}
    if row.role == "assistant":
        message: dict[str, Any] = {"role": "assistant", "content": row.content or ""}
        calls = (row.tool_calls or {}).get("calls")
        if calls:
            message["tool_calls"] = calls
        return message
    return {"role": row.role, "content": row.content or ""}
