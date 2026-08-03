# Spec: rozdział zachowania i zabezpieczeń persony

**Status:** zaakceptowane (2026-08-04)  
**Produkt:** goat — Multi-Persona Coaching App

## Problem

Pełny `default_prompt` gotowca (m.in. dietetyk) zawierał jednocześnie:
- zachowanie / styl / zakres pomocy (OK dla usera),
- reguły medyczne: lekarz, leki, „czego NIE robisz”, red flags (NIE dla usera).

User mógł to widzieć i edytować w formularzu persony.

## Decyzja

| Warstwa | Źródło | Widok API/UI | Edycja end-user |
|---|---|---|---|
| Platform preamble | kod backend | nie | nie |
| Safety overlay | `app_private.persona_template_safety` | nie | nie |
| Zachowanie | `personas.system_prompt` ← seed `persona_templates.default_prompt` | tak | tak |
| Twarde ograniczenia | `personas.persona_constraints` | nie (`PersonaOut`) | nie |

Skład promptu czatu/planu:

```
[PLATFORM PREAMBUŁ] + [ZABEZPIECZENIA GOTOWCA] + [ZACHOWANIE PERSONY] + opcjonalnie constraints + profil
```

## Baza

- `persona_templates`: tylko `default_prompt` (zachowanie) — SELECT publiczny jak dziś.
- `app_private.persona_template_safety(template_id, safety_prompt)` — brak GRANT dla `anon`/`authenticated`; odczyt wyłącznie przez `service_role` (backend).
- Reset środowiska: `supabase/reset_public.sql`, potem `0001_init.sql` + `0002_exercise_catalog.sql` (bez osobnego 0003).

## API / UI

- Formularz: pole „Jak ma się zachowywać” (dawniej system prompt) — treść behawioralna.
- Brak ekspozycji `safety_prompt` i `persona_constraints` w DTO.
- Create: wolno wysłać/edytować `system_prompt` (zachowanie); safety zawsze z szablonu po `base_template_id`.

## Poza zakresem

- Panel operatorski do edycji `persona_constraints` / safety.
- Column-level revoke na `personas.persona_constraints` (własny SELECT i tak widzi kolumnę w Data API — mitigacja: app nie używa Data API do person; dokumentacja świadomego ograniczenia MVP).
