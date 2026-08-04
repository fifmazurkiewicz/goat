"""Definicje narzędzi (tool calling) dostępnych dla `chat_model` w każdej rozmowie.

Dwa narzędzia, ta sama klasa wzorca (batch/częściowa aktualizacja, walidacja Pydantic,
błąd wraca do modelu jako tool response — NIGDY wyjątek/500):
- `log_result` — batch zapisu wyników (ai-pipeline.md sekcja 2).
- `update_user_profile` — częściowa aktualizacja profilu biometrycznego (ai-pipeline.md
  sekcja 0, ADR-11). Dostępne dla KAŻDEJ persony, nie tylko dietetyka/trenera — user może
  podać wagę w rozmowie z dowolną personą.

Schematy w formacie OpenRouter/OpenAI `tools=[...]` (function calling) — przekazywane
wprost do `ChatOrchestrator`/`app/llm/openrouter_client.py`, jeszcze niezaimplementowane
(patrz `app/domain/chat/orchestrator.py`).
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
            "Zapisuje dane biometryczne/cele usera (waga, wzrost, wiek, poziom aktywności, "
            "cel) podane w rozmowie. Wołaj gdy user poda którekolwiek z tych danych, "
            "niezależnie od tego jakiej persony/roli dotyczy rozmowa — profil jest "
            "wspólny. Częściowa aktualizacja: podawaj TYLKO pola, które user faktycznie "
            "właśnie podał, nigdy nie zgaduj brakujących."
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
            "Bez item_id = insert; z item_id = update własnej pozycji. Daty ISO wg "
            "[KONTEKST CZASOWY]."
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
                                "description": "Opcjonalne — zapis pozycji dla innej aktywnej persony (koordynacja zespołu).",
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
            "Uruchom pełną przebudowę planu (wszystkie aktywne persony + harmonizacja). "
            "Kosztowne — tylko gdy user jawnie prosi o wygenerowanie/przebudowę planu "
            "na tydzień lub miesiąc."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "period_type": {"type": "string", "enum": ["week", "month"]},
                "start_date": {"type": "string", "format": "date"},
            },
            "required": ["period_type", "start_date"],
            "additionalProperties": False,
        },
    },
}


def get_chat_tools() -> list[dict[str, Any]]:
    """Narzędzia dostępne dla `chat_model` w KAŻDEJ rozmowie (persona i general)."""
    return [
        LOG_RESULT_TOOL_SCHEMA,
        UPDATE_USER_PROFILE_TOOL_SCHEMA,
        GET_PLAN_TOOL_SCHEMA,
        UPSERT_PLAN_ITEMS_TOOL_SCHEMA,
        REBUILD_PLAN_TOOL_SCHEMA,
    ]


def build_profile_intake_instruction(profile: UserProfileOut | None) -> str | None:
    """Dynamiczny segment system promptu (ai-pipeline.md sekcja 0) — `None` gdy profil
    kompletny (nic do doklejenia). Wołane przez `ContextBuilder` przy KAŻDEJ wiadomości,
    nie tylko pierwszej — instrukcja znika sama, gdy dane się uzupełnią, bez potrzeby
    śledzenia "czy to już było pytane".
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
        "update_user_profile. Nie blokuj rozmowy, jeśli user nie chce podać któregoś "
        "pola — kontynuuj z tym, co masz."
    )
