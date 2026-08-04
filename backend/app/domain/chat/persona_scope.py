"""Zakres ról person — wspólne mapowanie dla routingu, promptu czatu i testów (ADR-13)."""

from __future__ import annotations

# Co persona MOŻE — klasyfikator routingu i blok [ZAKRES ROLI].
PERSONA_TYPE_SCOPE: dict[str, str] = {
    "personal_trainer": (
        "siła, hipertrofia, plan treningowy siłowy, technika podstawowych ćwiczeń, progresja obciążenia"
    ),
    "dietitian": (
        "żywienie, makroskładniki, posiłki, kalorie, nawodnienie, timing posiłków wokół treningu"
    ),
    "sport_psychologist": (
        "motywacja sportowa, stres startowy, koncentracja, nawyki mentalne w sporcie, rutyny przedmeczowe"
    ),
    "psychologist": (
        "ogólny dobrostan, stres codzienny, nawyki, równowaga życiowa w kontekście aktywności"
    ),
    "motor_coach": (
        "motoryka, plyometria, szybkość, dynamika, skok, bieganie, wydolność, mobilność, prewencja urazów"
    ),
    "badminton_coach": (
        "badminton: technika, taktyka, trening specyficzny, przygotowanie do meczu, footwork"
    ),
    "custom": "wyłącznie zakres opisany w zachowaniu tej persony",
}

# Czego persona NIE MOŻE — nie wypowiada się za inne role.
PERSONA_OUT_OF_SCOPE: dict[str, str] = {
    "personal_trainer": (
        "dieta, makro, posiłki → dietetyk; plyometria, bieganie, mobilność jako główny plan → trener motoryczny; "
        "technika/taktyka dyscypliny → trener dyscypliny; praca mentalna → psycholog sportowy"
    ),
    "dietitian": (
        "plany treningowe, periodyzacja, plyometria, technika sportowa, taktyka → trener personalny, "
        "trener motoryczny lub trener dyscypliny; psychika → psycholog"
    ),
    "sport_psychologist": (
        "plany treningowe, dieta, technika sportowa → właściwy trener lub dietetyk; terapia kliniczna → specjalista"
    ),
    "psychologist": (
        "plany treningowe, dieta, technika sportowa → właściwy trener lub dietetyk; stres startowy sportowy → "
        "psycholog sportowy; terapia kliniczna → specjalista"
    ),
    "motor_coach": (
        "pełny plan hipertrofii/siłowy → trener personalny; dieta → dietetyk; technika dyscypliny → trener "
        "dyscypliny; praca mentalna → psycholog sportowy"
    ),
    "badminton_coach": (
        "plan siłowy ogólny → trener personalny; motoryka poza badmintonem → trener motoryczny; "
        "dieta → dietetyk; psychika → psycholog sportowy"
    ),
    "custom": "wszystko poza zakresem opisanym w zachowaniu persony — wskaż inną personę z zespołu użytkownika",
}

SCOPE_BLOCK_HEADER = """[ZAKRES ROLI — OBOWIĄZKOWE]
Odpowiadasz WYŁĄCZNIE jako ta persona. Nie wypowiadasz się za inne persony i nie udzielasz porad
z ich obszarów — krótko wskaż właściwą rolę albo ogranicz się do wąskiego wkładu ze swojego zakresu."""

ROUTING_CLASSIFIER_RULES = """Zasady wyboru person:
- Każda persona odpowiada TYLKO ze swojego obszaru (patrz „zakres” przy każdej roli).
- NIGDY nie wybieraj persony, jeśli główny temat wiadomości leży poza jej zakresem.
- Przy wielu tematach w jednej wiadomości wybierz kilka person (max limit) — każda potem mówi
  wyłącznie ze swojego zakresu, nie za inne.
- Przykłady: dieta/makro → dietetyk; siła/hipertrofia → trener personalny; plyometria/bieganie/skok
  → trener motoryczny; badminton → trener badmintona; motywacja/stres startowy → psycholog sportowy."""


def build_persona_scope_block(persona_type: str) -> str:
    """Server-side granica roli — doklejana do każdego promptu czatu/planu."""
    scope = PERSONA_TYPE_SCOPE.get(persona_type, PERSONA_TYPE_SCOPE["custom"])
    out_of_scope = PERSONA_OUT_OF_SCOPE.get(persona_type, PERSONA_OUT_OF_SCOPE["custom"])
    return (
        f"{SCOPE_BLOCK_HEADER}\n"
        f"Twój zakres: {scope}.\n"
        f"Poza zakresem (nie odpowiadaj pełną poradą — wskaż personę): {out_of_scope}."
    )


def routing_persona_line(*, persona_id: str, persona_type: str, first_sentence: str) -> str:
    scope = PERSONA_TYPE_SCOPE.get(persona_type, PERSONA_TYPE_SCOPE["custom"])
    return f"- id={persona_id} | rola={persona_type} | zakres: {scope} | {first_sentence}"
