"""Kierownik zespołu — systemowa koordynacja sesji `general` (ADR-17).

User nie konfiguruje tej persony. W UI sesja nadal nazywa się „Ogólna rozmowa”.
Kierownik: (1) wybiera trenerów do konsultacji, (2) przygotowuje brief per trener,
(3) zbiera rekomendacje w jednej turze — trenerzy dostają brief + podsumowania poprzednich.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

import structlog

from app.domain.chat.routing import (
    CHAT_MAX_PERSONAS_PER_TURN,
    PersonaLike,
    RoutingResult,
    parse_multi_slash_command,
)

logger = structlog.get_logger(__name__)

TEAM_LEAD_SYSTEM = """Jesteś Kierownikiem Zespołu Trenerów w aplikacji coachingowej.
User widzi odpowiedzi poszczególnych trenerów — NIE widzi Ciebie.

Twoje zadanie na podstawie wiadomości usera:
1. Wybierz 1–{max_n} trenerów (po id), którzy powinni SEKWENCYJNIE odpowiedzieć.
2. Dla każdego wybranego trenera napisz krótki brief (po polsku): co ma uwzględnić,
   jakie dane zebrać, czy ma użyć narzędzi (log_result, get_plan, upsert_plan_items, rebuild_plan).
3. Jeśli user prosi o plan tygodnia/miesiąca — w briefie wskaż rebuild_plan u pierwszego
   trenera lub kierownika operacji (ten kto ma najszerszy obraz).
4. Wybierz WIĘCEJ niż jednego trenera tylko gdy pytanie realnie wymaga kilku ról.

Trenerzy NIE widzą nawzajem historii — dostaną Twój brief i podsumowania poprzednich
w tej turze. Koordynuj spójnie (np. dietetyk + trener przy planie)."""


@dataclass(frozen=True, slots=True)
class ConsultationPlan:
    persona_ids: list[str]
    invoked_via: Literal["slash_command", "multi_slash", "auto_routed", "team_lead"]
    content: str
    team_brief: str
    per_persona_briefs: dict[str, str] = field(default_factory=dict)
    status_message: str = "Uzgodniam z zespołem trenerów…"


class TeamLeadLLMProtocol(Protocol):
    async def complete_json(
        self, *, model: str, messages: list[dict], json_schema: dict, max_tokens: int = 200
    ) -> dict: ...


def _first_sentence(text: str, *, max_length: int = 160) -> str:
    stripped = text.strip()
    for sep in (".", "!", "?", "\n"):
        idx = stripped.find(sep)
        if idx != -1:
            return stripped[: idx + 1][:max_length]
    return stripped[:max_length]


class TeamLeadService:
    """Plan konsultacji przed turą person w sesji `general`."""

    def __init__(self, llm_client: TeamLeadLLMProtocol, *, chat_model: str) -> None:
        self._llm_client = llm_client
        self._chat_model = chat_model

    async def plan_consultation(
        self, *, message: str, active_personas: list[PersonaLike]
    ) -> ConsultationPlan:
        if not active_personas:
            raise ValueError("plan_consultation wymaga co najmniej jednej aktywnej persony.")

        slash_match = parse_multi_slash_command(message, active_personas)
        if slash_match is not None:
            personas, rest = slash_match
            invoked: Literal["slash_command", "multi_slash"] = (
                "multi_slash" if len(personas) > 1 else "slash_command"
            )
            names = ", ".join(p.slug for p in personas)
            return ConsultationPlan(
                persona_ids=[p.id for p in personas],
                invoked_via=invoked,
                content=rest,
                team_brief=f"User wskazał trenerów: {names}. Odpowiedz zgodnie z rolą.",
                per_persona_briefs={p.id: f"Odpowiedz jako {p.slug}." for p in personas},
                status_message="Przygotowuję odpowiedź wybranych trenerów…",
            )

        if len(active_personas) == 1:
            p = active_personas[0]
            return ConsultationPlan(
                persona_ids=[p.id],
                invoked_via="auto_routed",
                content=message,
                team_brief="Jeden aktywny trener — odpowiedz kompleksowo.",
                per_persona_briefs={p.id: "Odpowiedz na pytanie usera; użyj narzędzi gdy trzeba."},
                status_message=f"{p.slug} analizuje…",
            )

        return await self._classify_with_briefs(message=message, active_personas=active_personas)

    async def _classify_with_briefs(
        self, *, message: str, active_personas: list[PersonaLike]
    ) -> ConsultationPlan:
        ids = [p.id for p in active_personas]
        max_n = min(len(ids), CHAT_MAX_PERSONAS_PER_TURN)
        roster = "\n".join(
            f"- id={p.id} | slug={p.slug} | typ={p.type} | {_first_sentence(p.system_prompt)}"
            for p in active_personas
        )
        json_schema = {
            "name": "team_consultation",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "persona_ids": {
                        "type": "array",
                        "items": {"type": "string", "enum": ids},
                        "minItems": 1,
                        "maxItems": max_n,
                        "uniqueItems": True,
                    },
                    "team_brief": {"type": "string"},
                    "per_persona_briefs": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                    "status_message": {"type": "string"},
                },
                "required": ["persona_ids", "team_brief", "per_persona_briefs", "status_message"],
                "additionalProperties": False,
            },
        }
        system = TEAM_LEAD_SYSTEM.format(max_n=max_n) + "\n\nAktywni trenerzy:\n" + roster

        try:
            result = await self._llm_client.complete_json(
                model=self._chat_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": message},
                ],
                json_schema=json_schema,
                max_tokens=400,
            )
            raw_ids = result.get("persona_ids")
            if not isinstance(raw_ids, list):
                raw_ids = []
            normalized = [str(x) for x in raw_ids if str(x) in ids][:max_n]
            if not normalized:
                normalized = [ids[0]]

            briefs_raw = result.get("per_persona_briefs")
            briefs: dict[str, str] = {}
            if isinstance(briefs_raw, dict):
                for pid in normalized:
                    val = briefs_raw.get(pid)
                    if isinstance(val, str) and val.strip():
                        briefs[pid] = val.strip()

            team_brief = str(result.get("team_brief") or "Koordynacja zespołu trenerów.")
            status = str(result.get("status_message") or "Uzgodniam z zespołem trenerów…")

            return ConsultationPlan(
                persona_ids=normalized,
                invoked_via="team_lead",
                content=message,
                team_brief=team_brief,
                per_persona_briefs=briefs,
                status_message=status[:200],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("team_lead_consultation_failed", error=str(exc))
            return ConsultationPlan(
                persona_ids=[ids[0]],
                invoked_via="auto_routed",
                content=message,
                team_brief="Fallback — odpowiedz jako pierwszy dostępny trener.",
                per_persona_briefs={ids[0]: "Odpowiedz na pytanie usera."},
                status_message="Przygotowuję odpowiedź…",
            )


def build_consultation_user_message(
    *,
    user_content: str,
    team_brief: str,
    persona_brief: str | None,
    prior_summaries: list[tuple[str, str]],
) -> str:
    """Wzbogaca wiadomość usera o kontekst kierownika (niewidoczny w UI)."""
    parts = [user_content, "", "[BRIEF KIEROWNIKA ZESPOŁU]", team_brief]
    if persona_brief:
        parts.extend(["", "[TWOJE ZADANIE W TEJ TURZE]", persona_brief])
    if prior_summaries:
        parts.append("")
        parts.append("[REKOMENDACJE INNYCH TRENERÓW W TEJ TURZE]")
        for label, summary in prior_summaries:
            parts.append(f"- {label}: {summary}")
    return "\n".join(parts)


def consultation_to_routing(plan: ConsultationPlan) -> RoutingResult:
    invoked: Literal["slash_command", "multi_slash", "auto_routed"] = (
        plan.invoked_via
        if plan.invoked_via in ("slash_command", "multi_slash", "auto_routed")
        else "auto_routed"
    )
    return RoutingResult(persona_ids=plan.persona_ids, invoked_via=invoked, content=plan.content)
