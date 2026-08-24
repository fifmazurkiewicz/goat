# Team briefing — 2026-08-04: safety prompt + migration reset

## What's changing

1. **Persona prompt split**
   - User edits only **behavior** ("How it should behave" / `system_prompt`).
   - **Doctor / medications / red flags / "what you do NOT do"** → `app_private.persona_template_safety` (invisible in API/UI).
   - `persona_constraints` still system-level (not in DTO).

2. **Migrations**
   - Removed `0003_professional_templates.sql` (content in `0001`).
   - New wipe: `supabase/reset_public.sql` (manually before re-init).
   - Order: wipe → `0001_init.sql` → `0002_exercise_catalog.sql`.
   - Docs: `cloud-setup.md` Step 4 updated.

3. **Backend**
   - `PREAMBLE_VERSION = 2`
   - Chat + plan attach safety via `service_role_connection`
   - Spec: `docs/superpowers/specs/2026-08-04-persona-safety-prompt-design.md`

## What to do locally / in the cloud

1. Supabase SQL Editor: run `reset_public.sql`
2. Run `0001_init.sql`, then `0002_exercise_catalog.sql`
3. Redeploy backend (Render) after merge — without this the old API has no safety
4. Smoke: add dietitian → in UI **no** block about doctor/medications; in behavior there is style/scope of help

## Audit (team synthesis)

In parallel: [Architecture](9667dfc1-40ea-45ac-8e09-5428c667d0bf), [Security](71dd8db8-bb81-4933-b026-bbd2dbf2164e), [Code review](2f5c2f82-7f8e-4a18-bb54-d5a508163059), [UX](b4bba55d-fa89-4166-becd-5a8cdf5e1dc7).

| Finding | Status after implementation |
|---|---|
| Safety in editable `default_prompt` | ✅ separated in `0001` + `app_private` |
| PlanOrchestrator without preamble/safety | ✅ attaches `build_system_prompt` + safety |
| PostgREST may UPDATE `persona_constraints` | ✅ trigger `guard_persona_constraints` |
| Clone copies constraints | ✅ `None` on clone |
| UX: "system prompt" / full seed with prohibitions | ✅ "Style and scope of help" + hint of layer |
| Full move of `persona_constraints` to `internal` (SELECT hide) | ⏳ backlog (Data API still sees the column on own rows) |
| Template preview without full-text pasting | ⏳ UX backlog |

MCP Supabase in this session **doesn't see** a project named `goat` — wipe/init must be triggered manually in the SQL Editor of the target project.
