"""Tool definitions (tool calling) available for `chat_model` in every conversation.

Two tools, same pattern class (batch/partial update, Pydantic validation, error returns
to the model as a tool response — NEVER an exception/500):
- `log_result` — batch result logging (ai-pipeline.md section 2).
- `update_user_profile` — partial biometric profile update (ai-pipeline.md section 0,
  ADR-11). Available for EVERY persona, not only dietitian/trainer — user can give
  weight in a conversation with any persona.

Schemas in OpenRouter/OpenAI `tools=[...]` (function calling) format — passed directly
to `ChatOrchestrator`/`app/llm/openrouter_client.py`, not yet implemented (see
`app/domain/chat/orchestrator.py`).
"""

from __future__ import annotations

from typing import Any

from app.models.schemas import CRITICAL_PROFILE_FIELDS, UserProfileOut

LOG_RESULT_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "log_result",
        "description": (
            "Zapisuje 1-N faktycznie zaraportowanych przez użytkownika wyników "
            "(trening, dieta, pomiary) w JEDNYM wywołaniu (batch — ADR-6). Wołaj "
            "WYŁĄCZNIE gdy user jawnie raportuje faktyczny wynik, nigdy nie zgaduj/nie "
            "fabrykuj wartości. Trening z 5 ćwiczeniami = 5 wpisów w jednym wywołaniu. "
            "Daty względne („wczoraj”) przelicz na ISO YYYY-MM-DD wg [KONTEKST CZASOWY]. "
            "Bieganie/kondycja/siła: category=strength (np. metric run_distance_km, "
            "run_time_min). Dieta: diet. Badminton: badminton. Nie wymyślaj category "
            "poza enumem."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entries": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": [
                                    "strength",
                                    "diet",
                                    "swimming",
                                    "triathlon",
                                    "badminton",
                                    "custom",
                                ],
                            },
                            "metric": {
                                "type": "string",
                                "description": "Klucz metryki, np. 'weight_kg', 'bench_press_1rm'.",
                            },
                            "value": {"type": "number"},
                            "unit": {"type": "string"},
                            "date": {
                                "type": "string",
                                "format": "date",
                                "description": "Data wyniku, ISO 8601 (YYYY-MM-DD).",
                            },
                            "notes": {"type": "string"},
                        },
                        "required": ["category", "metric", "value", "date"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["entries"],
            "additionalProperties": False,
        },
    },
}

UPDATE_USER_PROFILE_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "update_user_profile",
        "description": (
            "Zapisuje trwały profil usera (waga, wzrost, data urodzenia, płeć, poziom "
            "aktywności, cel, notatki). ZASADY: (1) wołaj TYLKO gdy user jawnie poda "
            "konkretną wartość w tej wiadomości — nie zgaduj, nie wnioskuj z kontekstu; "
            "(2) częściowa aktualizacja — podawaj wyłącznie pola, które user właśnie "
            "podaje; (3) `notes` — gdy user poda trwałą informację (kontuzja, alergia, "
            "preferencje, ograniczenia), która nie pasuje do pól strukturalnych; "
            "(4) profil jest wspólny dla całego konta — niezależnie od persony/roli; "
            "(5) nie zapisuj jednorazowych wyników treningu (do tego służy log_result)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "height_cm": {"type": "number", "description": "Wzrost w centymetrach (100-250)."},
                "weight_kg": {"type": "number", "description": "Waga w kilogramach (20-400)."},
                "date_of_birth": {
                    "type": "string",
                    "format": "date",
                    "description": "Data urodzenia, format ISO 8601 (YYYY-MM-DD).",
                },
                "sex": {"type": "string", "enum": ["male", "female", "other"]},
                "activity_level": {
                    "type": "string",
                    "enum": ["sedentary", "light", "moderate", "active", "very_active"],
                },
                "primary_goal": {
                    "type": "string",
                    "enum": [
                        "lose_weight",
                        "build_muscle",
                        "improve_endurance",
                        "general_health",
                        "sport_specific",
                    ],
                },
                "notes": {
                    "type": "string",
                    "description": "Dodatkowy wolny kontekst niepasujący do pól strukturalnych.",
                },
            },
            "additionalProperties": False,
        },
    },
}


GET_PLAN_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_plan",
        "description": (
            "Odczytaj aktualny plan użytkownika (zakładka Plany). Wołaj gdy user pyta "
            "co ma w planie / kalendarzu, albo PRZED edycją. Opcjonalny zakres dat."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "format": "date"},
                "end_date": {"type": "string", "format": "date"},
            },
            "additionalProperties": False,
        },
    },
}

UPSERT_PLAN_ITEMS_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "upsert_plan_items",
        "description": (
            "Dopisz lub zaktualizuj pozycje dnia w zakładce Plany. Wołaj TYLKO gdy user "
            "jawnie prosi o zapisanie treningu/diety w planie (nie gdy dostajesz samą radę). "
            "Przy prośbie o konkretny dzień zapisuj WYŁĄCZNIE tę datę — nie przebudowuj tygodnia/miesiąca. "
            "Bez item_id = insert; z item_id = update własnej pozycji. Daty ISO wg "
            "[KONTEKST CZASOWY]. Jako Goat (kierownik): w każdej pozycji PODAJ persona_id "
            "aktywnej persony z rosteru — masz ostateczny głos i możesz poprawiać cudze karty."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entries": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_id": {
                                "type": "string",
                                "description": "Opcjonalne — update istniejącego plan_item.",
                            },
                            "item_date": {"type": "string", "format": "date"},
                            "item_type": {"type": "string"},
                            "title": {"type": "string"},
                            "columns": {"type": "array", "items": {"type": "string"}},
                            "rows": {"type": "array", "items": {"type": "object"}},
                            "notes": {"type": "string"},
                            "persona_id": {
                                "type": "string",
                                "description": (
                                    "Opcjonalne — zapis pozycji dla innej aktywnej persony (koordynacja zespołu)."
                                ),
                            },
                        },
                        "required": ["item_date", "item_type", "title", "columns", "rows"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["entries"],
            "additionalProperties": False,
        },
    },
}

REBUILD_PLAN_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "rebuild_plan",
        "description": (
            "Uruchom pełną przebudowę planu (aktywne persony + harmonizacja). "
            "Kosztowne — gdy user jawnie prosi o wygenerowanie/przebudowę/aktualizację "
            "planu na tydzień lub miesiąc. NIGDY dla pytania o jeden konkretny dzień. "
            "Przekaż user_brief z twardymi ograniczeniami "
            "(np. „bez badmintona — tylko siłownia i bieganie”)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "period_type": {"type": "string", "enum": ["week", "month"]},
                "start_date": {"type": "string", "format": "date"},
                "user_brief": {
                    "type": "string",
                    "description": (
                        "Twarde ograniczenia / cel przebudowy od usera "
                        "(np. zero badmintona, fokus siła+bieg do września)."
                    ),
                },
                "confirmed": {
                    "type": "boolean",
                    "description": (
                        "true dopiero gdy user potwierdzi przebudowę (tak / potwierdzam). "
                        "Pierwsze wywołanie bez confirmed — nie uruchamia joba."
                    ),
                },
            },
            "required": ["period_type", "start_date"],
            "additionalProperties": False,
        },
    },
}

CONSULT_PERSONA_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "consult_persona",
        "description": (
            "Rzadko: dopytaj jednego aktywnego trenera (za kulisami) TYLKO gdy potrzebujesz "
            "szczegółu z JEGO zakresu, którego nie domkniesz sam. Nie używaj przy prostych "
            "wiadomościach ani przy samej korekcie/przebudowie planu (tam: rebuild_plan). "
            "Motoryka/plyometria/bieganie/skok → slug motor_coach; dieta/makro → dietitian; "
            "siła/hipertrofia → personal_trainer. Nie wołaj złej roli. Po wyniku odpowiedz "
            "userowi SAM jako Goat — nie cytuj trenera w całości."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "Slug aktywnej persony z rosteru.",
                },
                "question": {
                    "type": "string",
                    "description": "Konkretne pytanie / brief do trenera.",
                },
            },
            "required": ["slug", "question"],
            "additionalProperties": False,
        },
    },
}


def get_chat_tools() -> list[dict[str, Any]]:
    """Tools available for `chat_model` in EVERY conversation (persona and general)."""
    return [
        LOG_RESULT_TOOL_SCHEMA,
        UPDATE_USER_PROFILE_TOOL_SCHEMA,
        GET_PLAN_TOOL_SCHEMA,
        UPSERT_PLAN_ITEMS_TOOL_SCHEMA,
        REBUILD_PLAN_TOOL_SCHEMA,
    ]


def get_trainer_chat_tools() -> list[dict[str, Any]]:
    """Trainers — without rebuild_plan (harmonization is triggered by Goat)."""
    return [t for t in get_chat_tools() if t.get("function", {}).get("name") != "rebuild_plan"]


def get_consult_persona_tools() -> list[dict[str, Any]]:
    """Nested `consult_persona` — read-only (no writes to results / profile / plan)."""
    return [GET_PLAN_TOOL_SCHEMA]


TEAM_LEAD_CHAT_TOOL_NAMES = frozenset(
    {
        "get_plan",
        "rebuild_plan",
        "update_user_profile",
        "consult_persona",
        "upsert_plan_items",
        "log_result",
    }
)


def get_team_lead_plan_tools() -> list[dict[str, Any]]:
    """Goat (team lead) — plan (upsert for any persona), profile, and `log_result`.

    Results reported in a `general` session go to Goat, not to a trainer — it writes
    them itself with `source_persona_id=NULL` (spec 2026-08-17, ADR-17 revision).
    """
    return [
        t
        for t in [*get_chat_tools(), CONSULT_PERSONA_TOOL_SCHEMA]
        if t.get("function", {}).get("name") in TEAM_LEAD_CHAT_TOOL_NAMES
    ]


def build_profile_intake_instruction(profile: UserProfileOut | None) -> str | None:
    """Dynamic system prompt segment (ai-pipeline.md section 0) — `None` when the
    profile is complete (nothing to append). Called by `ContextBuilder` on EVERY
    message, not only the first — the instruction disappears on its own when data is
    filled in, without needing to track "has this already been asked".
    """
    missing = list(CRITICAL_PROFILE_FIELDS) if profile is None else profile.missing_critical_fields
    if not missing:
        return None

    missing_labels = {
        "height_cm": "wzrost",
        "weight_kg": "waga",
        "date_of_birth": "data urodzenia / wiek",
        "activity_level": "poziom aktywności",
        "primary_goal": "główny cel",
    }
    missing_pl = ", ".join(missing_labels[field] for field in missing)

    return (
        "[KONTEKST: PROFIL UŻYTKOWNIKA NIEKOMPLETNY]\n"
        f"Brakuje: {missing_pl}. Zanim przejdziesz do właściwego coachingu, dopytaj "
        "naturalnie o brakujące dane w 1-2 pierwszych wiadomościach tej rozmowy (nie "
        "jako sztywna ankieta). Gdy user je poda, zapisz je narzędziem "
        "update_user_profile (tylko jawnie podane wartości, bez zgadywania). "
        "Nie blokuj rozmowy, jeśli user nie chce podać któregoś "
        "pola — kontynuuj z tym, co masz."
    )
