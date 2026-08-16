"""Kierownik zespołu — systemowa koordynacja sesji `general` (ADR-17).

User nie konfiguruje tej persony. W UI sesja nadal nazywa się „Ogólna rozmowa”.
Produkcja: jedna tura `TeamLeadSpeaker` z `consult_persona`; slash → bezpośrednia persona.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.chat.routing import PersonaLike

TEAM_LEAD_NAME = "Goat"
TEAM_LEAD_ROLE_LABEL = "Kierownik Zespołu"
TEAM_LEAD_DISPLAY_LABEL = f"{TEAM_LEAD_NAME} · {TEAM_LEAD_ROLE_LABEL}"
TEAM_LEAD_PERSONA_ID = "__team_lead__"

MAX_CONSULTS_PER_TURN = 5

TEAM_LEAD_TURN_BEHAVIOR = """Jesteś Goat — Kierownikiem Zespołu Trenerów. User rozmawia WYŁĄCZNIE z Tobą.
Trenerzy pracują za kulisami przez narzędzie consult_persona. Nie udawaj specjalistów z rosteru —
gdy potrzebujesz szczegółu z ich zakresu, wołaj consult_persona z właściwym slugiem z rosteru.

Zasady consult_persona:
- Roster poniżej to JEDYNE persony tego usera (te, które sam utworzył i ma aktywne). Nie wymyślaj ról spoza listy.
- Zawsze podawaj slug z rosteru — NIE typ persony (motor_coach, dietitian, custom) jako slug.
- Dobierz slug do tematu po polu „zakres” (i opisie zachowania) przy każdej osobie z rosteru.
- Nie wołaj złej persony. Po tool response odpowiedz SAM — zwięźle, możesz wspomnieć z kim uzgodniłeś,
  ale nie wklejaj odpowiedzi trenera w całości.
- User prosi „niech każdy” / o skład zespołu → consult_persona dla KAŻDEGO slug z rosteru, potem jedna odpowiedź.
- Plan tygodnia/miesiąca / przebudowa → rebuild_plan (zakładka Plany). Szczegół merytoryczny w tej samej
  wiadomości → dodatkowo consult_persona.
- update_user_profile tylko gdy user jawnie podaje dane. Nie wołaj log_result ani upsert_plan_items.
Bezpośrednia rozmowa usera z trenerem: tylko /slug."""

TEAM_LEAD_PLAN_BEHAVIOR = TEAM_LEAD_TURN_BEHAVIOR


PERSONA_TYPE_LABELS_PL: dict[str, str] = {
    "personal_trainer": "Trener personalny",
    "dietitian": "Dietetyk",
    "sport_psychologist": "Psycholog sportowy",
    "psychologist": "Psycholog",
    "motor_coach": "Trener motoryczny",
    "badminton_coach": "Trener badmintona",
    "custom": "Własna persona",
    "team_lead": TEAM_LEAD_ROLE_LABEL,
}


def is_direct_persona_invocation(invoked_via: str | None) -> bool:
    """User rozmawia bezpośrednio z personą — tylko slash / multi-slash."""
    return invoked_via in ("slash_command", "multi_slash")


def persona_display_label(persona: PersonaLike) -> str:
    role = PERSONA_TYPE_LABELS_PL.get(persona.type, persona.type)
    name = (persona.name or "").strip()
    if name.lower() == role.lower():
        return role
    return f"{name} · {role}"


def resolve_persona_by_slug(
    slug: str, active_personas: list[PersonaLike]
) -> PersonaLike | None:
    needle = slug.strip().lstrip("/").lower()
    if not needle:
        return None
    return next((p for p in active_personas if p.slug.lower() == needle), None)


def goat_consult_status_message(persona: PersonaLike) -> str:
    return f"Goat konsultuje z {persona_display_label(persona)}…"


_HINT_STOPWORDS = frozenset(
    {
        "plan",
        "trening",
        "ćwiczen",
        "cwiczen",
        "zakres",
        "opisany",
        "zachowaniu",
        "persony",
        "wyłącznie",
        "wylacznie",
        "podstawowych",
    }
)


def _persona_scope_text(persona: PersonaLike) -> str:
    from app.domain.chat.persona_scope import PERSONA_TYPE_SCOPE

    scope = PERSONA_TYPE_SCOPE.get(persona.type, PERSONA_TYPE_SCOPE["custom"])
    prompt = (getattr(persona, "system_prompt", None) or "").strip()
    name = (getattr(persona, "name", None) or "").strip()
    return " ".join(part for part in (scope, persona.slug, name, prompt) if part)


def _hint_tokens(text: str) -> list[str]:
    raw = text.lower().replace(":", " ").replace("/", " ").replace("—", " ").replace("-", " ")
    tokens: list[str] = []
    for part in raw.replace(",", " ").split():
        cleaned = part.strip(".,;()[]`'")
        if len(cleaned) < 5 or cleaned in _HINT_STOPWORDS:
            continue
        tokens.append(cleaned)
    return tokens


def _token_hits_message(token: str, message: str) -> bool:
    if token in message:
        return True
    stem = token[:6] if len(token) >= 6 else token
    return len(stem) >= 5 and stem in message


def consult_scope_hint(*, message: str, active_personas: list[PersonaLike]) -> str | None:
    """Wskazówka tylko spośród person z rosteru tego usera — bez hardcoded ról."""
    lower = message.lower()
    matched = [
        p
        for p in active_personas
        if any(_token_hits_message(tok, lower) for tok in _hint_tokens(_persona_scope_text(p)))
    ]
    if not matched:
        return None
    slugs = ", ".join(f"`{p.slug}`" for p in matched)
    return (
        f"Wskazówka zakresu: treść pasuje do person z rosteru tego usera: {slugs}. "
        "Wołaj wyłącznie te slugi — nie role spoza listy."
    )


def build_goat_turn_prompt(*, active_personas: list[PersonaLike], user_message: str) -> str:
    from app.domain.chat.persona_scope import PERSONA_TYPE_SCOPE

    lines = [
        TEAM_LEAD_TURN_BEHAVIOR,
        "",
        "Roster aktywnych trenerów TEGO usera (jedyny dozwolony zestaw slug → consult_persona):",
    ]
    for p in active_personas:
        scope = PERSONA_TYPE_SCOPE.get(p.type, PERSONA_TYPE_SCOPE["custom"])
        extra = ""
        if p.type == "custom":
            prompt_head = (getattr(p, "system_prompt", None) or "").strip().split("\n")[0][:160]
            if prompt_head:
                extra = f" | zachowanie: {prompt_head}"
        lines.append(
            f"- slug=`{p.slug}` | {persona_display_label(p)} | zakres: {scope}{extra}"
        )
    hint = consult_scope_hint(message=user_message, active_personas=active_personas)
    if hint:
        lines.extend(["", hint])
    if user_requests_all_trainers(user_message):
        slugs = ", ".join(f"`{p.slug}`" for p in active_personas)
        lines.extend(["", f"User prosi o cały zespół — skonsultuj wszystkich: {slugs}."])
    if user_requests_plan_rebuild(user_message):
        lines.extend(["", "User prosi o plan — wołaj rebuild_plan."])
    return "\n".join(lines)


def user_requests_all_trainers(message: str) -> bool:
    """Heurystyka: user prosi o wypowiedź każdego trenera / całego składu."""
    lower = message.lower()
    needles = (
        "niech każdy",
        "niech kazdy",
        "niech każdy powie",
        "niech kazdy powie",
        "każdy napis",
        "kazdy napis",
        "każdy powie",
        "kazdy powie",
        "każdy coś",
        "kazdy cos",
        "coś od siebie",
        "cos od siebie",
        "wszyscy trener",
        "cały zespół",
        "caly zespol",
        "od każdego",
        "od kazdego",
        "przedstaw się",
        "przedstawcie się",
        "przedstaw sie",
        "przedstawcie sie",
    )
    if any(n in lower for n in needles):
        return True
    if ("skład" in lower or "sklad" in lower) and ("zespół" in lower or "zespol" in lower):
        return any(
            w in lower
            for w in ("trener", "person", "persony", "kto", "jakich", "składa", "sklada")
        )
    if "z jakich person" in lower or "z jakich trener" in lower:
        return True
    return False


def user_requests_plan_rebuild(message: str) -> bool:
    lower = message.lower()
    needles = (
        "plan na",
        "ułóż plan",
        "ulóż plan",
        "ułóz plan",
        "zharmonizowany plan",
        "przebuduj plan",
        "plan tygodnia",
        "plan miesiąca",
        "generuj plan",
        "stwórz plan",
        "zaplanuj mi",
        "harmoniz",
        "w zakładce plany",
    )
    return any(n in lower for n in needles)


def is_plan_coordination_only(message: str) -> bool:
    """Heurystyka: prośba głównie o plan, bez osobnego pytania merytorycznego do trenera."""
    if not user_requests_plan_rebuild(message):
        return False
    lower = message.lower()
    detail_markers = (
        "co jeść",
        "co jem",
        "makro",
        "technika",
        "jak trenować",
        " ćwiczen",
        "contuzj",
        "kontuzj",
        "psychik",
        "motywac",
    )
    return not any(m in lower for m in detail_markers)


@dataclass(frozen=True, slots=True)
class TeamLeadSpeaker:
    """Wirtualna persona Goata — widoczna w UI przy operacjach na planie."""

    id: str = TEAM_LEAD_PERSONA_ID
    name: str = TEAM_LEAD_NAME
    type: str = "team_lead"
    system_prompt: str = TEAM_LEAD_TURN_BEHAVIOR
    base_template_id: None = None
    persona_constraints: None = None
