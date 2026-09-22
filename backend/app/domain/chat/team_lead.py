"""Team lead — system coordination for `general` sessions (ADR-17).

The user does not configure this persona. In the UI the session is still called "General conversation".
Production: one `TeamLeadSpeaker` turn with `consult_persona`; slash → direct persona.
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
Domyślnie odpowiadaj SAMODZIELNIE — szybko, bez consult_persona. Trenerzy są za kulisami tylko gdy
naprawdę potrzebujesz szczegółu specjalistycznego spoza Twojej ogólnej wiedzy coachingowej.

Kiedy NIE wołaj consult_persona (odpowiedz sam):
- proste rzeczy: powitanie, status, potwierdzenie, „ok”, dopytanie o preferencje;
- korekta / przebudowa / aktualizacja planu, skargi na plan („widzę badminton”, „bez X”);
- ogólne wskazówki, które znasz jako kierownik (motywacja, struktura tygodnia, priorytety).

Kiedy wolno consult_persona (rzadko):
- konkretny szczegół z zakresu persony z rosteru (makra, plyometria, technika dyscypliny, psychika startowa),
  którego nie da się sensownie domknąć bez eksperta;
- user jawnie prosi „niech każdy” / o skład zespołu → consult_persona dla KAŻDEGO slug z rosteru.

Zasady consult_persona (gdy już wołasz):
- Roster poniżej = JEDYNE persony tego usera. Nie wymyślaj ról spoza listy.
- Zawsze slug z rosteru — NIE typ (motor_coach, dietitian, custom) jako slug.
- Dobierz slug po polu „zakres” / zachowaniu. Nie wołaj złej persony.
- Po tool response odpowiedz SAM — zwięźle; nie wklejaj odpowiedzi trenera w całości.

Plan:
- Prośba o trening/plan na KONKRETNY dzień („dzisiaj”, „jutro”, dzień tygodnia lub data) →
  obsłuż TYLKO ten dzień. Najpierw get_plan z start_date=end_date tą datą; jeśli user chce
  zapisu/zmiany, użyj upsert_plan_items wyłącznie dla tej daty. NIGDY nie wołaj rebuild_plan.
- Ogólne „ułóż/zaplanuj mi trening” bez dnia, tygodnia ani miesiąca → najpierw zapytaj po polsku:
  „Na który dzień, tydzień czy miesiąc mam przygotować plan?” Nie wołaj żadnego narzędzia.
- Tygodnia/miesiąca / przebudowa / pełna aktualizacja planu → TYLKO rebuild_plan (zakładka Plany).
- NIE uruchamiaj pełnej przebudowy po cichu: pierwsze rebuild_plan (user zobaczy
  „Potwierdź przebudowę planu”). Enqueue dopiero gdy user napisze „tak” — parametr
  confirmed w narzędziu jest ignorowany.
  gdy user napisze „tak” / „potwierdzam”.
- Ograniczenia usera (np. „bez badmintona”, „tylko siła i bieg”) wstaw w user_brief przy rebuild_plan.
- Przy samej korekcie planu NIE wołaj consult_persona.
- Szczegół merytoryczny W TEJ SAMEJ wiadomości co plan (np. „i co jeść”) → dopiero wtedy ewentualny consult.
- Persony mogą zapisywać szkice (upsert). Ty masz OSTATECZNY GŁOS: upsert_plan_items z persona_id
  aktywnej persony albo rebuild_plan z briefem, gdy trzeba przebudować całość.

Wyniki:
- User raportuje faktyczny wynik (km, serie/ciężary, waga, czas) → zapisz SAM przez
  log_result (batch: cały trening w JEDNYM wywołaniu). Nie odsyłaj do trenera.
- Nigdy nie zgaduj ani nie fabrykuj wartości — zapisuj wyłącznie to, co user podał.
- Daty względne („wczoraj”) przelicz na ISO wg [KONTEKST CZASOWY].
- Po zapisie potwierdź krótko, co wylądowało w bazie.

update_user_profile tylko gdy user jawnie podaje dane (trwały profil, nie jednorazowy wynik).
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
    """User talks directly to a persona — slash / multi-slash only."""
    return invoked_via in ("slash_command", "multi_slash")


def persona_display_label(persona: PersonaLike) -> str:
    role = PERSONA_TYPE_LABELS_PL.get(persona.type, persona.type)
    name = (persona.name or "").strip()
    if name.lower() == role.lower():
        return role
    return f"{name} · {role}"


def resolve_persona_by_slug(slug: str, active_personas: list[PersonaLike]) -> PersonaLike | None:
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
    """Hint only among personas from this user's roster — no hardcoded roles."""
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
        lines.append(f"- slug=`{p.slug}` | {persona_display_label(p)} | zakres: {scope}{extra}")
    if user_requests_single_day_plan(user_message):
        lines.extend(
            [
                "",
                "User prosi o konkretny dzień. Użyj get_plan WYŁĄCZNIE dla tej daty "
                "(data startu = data końca z KONTEKSTU CZASOWEGO), a jeśli chce zmiany "
                "zapisu — upsert_plan_items WYŁĄCZNIE dla tej daty. "
                "NIE wołaj rebuild_plan ani consult_persona.",
            ]
        )
    elif user_requests_vague_plan(user_message):
        lines.extend(
            [
                "",
                "User chce plan, ale nie podał okresu. Zadaj dokładnie pytanie: "
                "„Na który dzień, tydzień czy miesiąc mam przygotować plan?” "
                "NIE wołaj żadnego narzędzia ani consult_persona.",
            ]
        )
    elif is_plan_coordination_only(user_message):
        lines.extend(
            [
                "",
                "User prosi o plan/korektę planu — wołaj TYLKO rebuild_plan "
                "(user_brief = twarde ograniczenia, np. bez badmintona). "
                "NIE wołaj consult_persona.",
            ]
        )
    else:
        hint = consult_scope_hint(message=user_message, active_personas=active_personas)
        if hint:
            lines.extend(["", hint])
        if user_requests_all_trainers(user_message):
            slugs = ", ".join(f"`{p.slug}`" for p in active_personas)
            lines.extend(["", f"User prosi o cały zespół — skonsultuj wszystkich: {slugs}."])
        elif user_requests_plan_rebuild(user_message):
            lines.extend(
                [
                    "",
                    "User prosi o plan — wołaj rebuild_plan z user_brief. "
                    "consult_persona tylko jeśli w tej samej wiadomości jest osobne pytanie eksperckie.",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "Preferuj odpowiedź samodzielną. NIE wołaj consult_persona, "
                    "chyba że pytanie wymaga szczegółu z zakresu persony z rosteru.",
                ]
            )
    return "\n".join(lines)


def user_requests_all_trainers(message: str) -> bool:
    """Heuristic: user asks every trainer / the full roster to speak."""
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
        return any(w in lower for w in ("trener", "person", "persony", "kto", "jakich", "składa", "sklada"))
    if "z jakich person" in lower or "z jakich trener" in lower:
        return True
    return False


def user_requests_plan_rebuild(message: str) -> bool:
    lower = message.lower()
    if user_requests_single_day_plan(lower):
        return False
    needles = (
        "plan na",
        "zharmonizowany plan",
        "przebuduj plan",
        "przebudow",
        "plan tygodnia",
        "plan miesiąca",
        "generuj plan",
        "stwórz plan",
        "zaktualizuj plan",
        "aktualizuj plan",
        "w aktualnym planie",
        "w planie widzę",
        "harmoniz",
        "w zakładce plany",
    )
    return any(n in lower for n in needles)


def user_requests_single_day_plan(message: str) -> bool:
    """A plan request with an explicit single-day anchor, never a full regeneration."""
    lower = message.lower()
    if not any(word in lower for word in ("plan", "trening", "trenow", "ćwiczen", "cwiczen", "siłown", "silown")):
        return False
    day_needles = (
        "dzisiaj",
        "dziś",
        "dzis",
        "jutro",
        "pojutrze",
        "poniedział",
        "poniedzial",
        "wtorek",
        "środ",
        "srod",
        "czwartek",
        "piątek",
        "piatek",
        "sobot",
        "niedziel",
    )
    return any(needle in lower for needle in day_needles)


def user_requests_vague_plan(message: str) -> bool:
    """A creation request without an explicit planning period or a particular day."""
    lower = message.lower()
    if user_requests_single_day_plan(lower) or user_requests_plan_rebuild(lower):
        return False
    needles = (
        "ułóż plan",
        "ulóż plan",
        "ułóz plan",
        "ułóż mi",
        "ulóż mi",
        "ułóz mi",
        "zaplanuj mi",
        "stwórz plan",
        "generuj plan",
    )
    return any(needle in lower for needle in needles)


def user_confirms_rebuild(message: str) -> bool:
    """Next-turn explicit confirm after `rebuild_plan` returned `needs_confirm`."""
    text = " ".join((message or "").strip().lower().split())
    if not text:
        return False
    if text in {"tak", "tak.", "potwierdzam", "potwierdzam.", "potwierdź", "potwierdz"}:
        return True
    return text.startswith(("tak,", "tak ", "tak.", "potwierdzam", "potwierdź"))


def plan_brief_excludes_persona_type(brief: str, persona_type: str) -> bool:
    """Whether the user's brief excludes generating input for a given role (e.g. no badminton)."""
    lower = (brief or "").lower()
    if not lower:
        return False
    if persona_type == "badminton_coach":
        if "badminton" not in lower:
            return False
        exclusion = (
            "bez",
            "zero",
            "żadn",
            "zadn",
            "wyklucz",
            "nie planuj",
            "usuń",
            "usun",
            "wywal",
            "bez jakiegokolwiek",
        )
        return any(w in lower for w in exclusion)
    return False


def is_plan_coordination_only(message: str) -> bool:
    """Heuristic: request is mainly about the plan, without a separate substantive question to a trainer."""
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
    """Virtual Goat persona — visible in the UI during plan operations."""

    id: str = TEAM_LEAD_PERSONA_ID
    name: str = TEAM_LEAD_NAME
    type: str = "team_lead"
    system_prompt: str = TEAM_LEAD_TURN_BEHAVIOR
    base_template_id: None = None
    persona_constraints: None = None
