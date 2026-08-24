# Spec: persona behavior and safety split

**Status:** accepted (2026-08-04)  
**Product:** goat — Multi-Persona Coaching App

## Problem

The full `default_prompt` of the template (including dietitian) contained at once:
- behavior / style / scope of help (OK for user),
- medical rules: doctor, medications, "what you do NOT do", red flags (NOT for user).

The user could see and edit this in the persona form.

## Decision

| Layer | Source | API/UI view | End-user edit |
|---|---|---|---|
| Platform preamble | backend code | no | no |
| Safety overlay | `app_private.persona_template_safety` | no | no |
| Behavior | `personas.system_prompt` ← seed `persona_templates.default_prompt` | yes | yes |
| Hard constraints | `personas.persona_constraints` | no (`PersonaOut`) | no |

Chat/plan prompt composition:

```
[PLATFORM PREAMBLE] + [TEMPLATE SAFETY] + [PERSONA BEHAVIOR] + optional constraints + profile
```

## Database

- `persona_templates`: only `default_prompt` (behavior) — public SELECT as today.
- `app_private.persona_template_safety(template_id, safety_prompt)` — no GRANT for `anon`/`authenticated`; read only via `service_role` (backend).
- Environment reset: `supabase/reset_public.sql`, then `0001_init.sql` + `0002_exercise_catalog.sql` (without a separate 0003).

## API / UI

- Form: "How it should behave" field (formerly system prompt) — behavioral content.
- No exposure of `safety_prompt` and `persona_constraints` in DTO.
- Create: may send/edit `system_prompt` (behavior); safety always from template by `base_template_id`.

## Out of scope

- Operator panel for editing `persona_constraints` / safety.
- Column-level revoke on `personas.persona_constraints` (own SELECT still sees the column in Data API — mitigation: app doesn't use Data API for personas; documentation of conscious MVP limitation).
