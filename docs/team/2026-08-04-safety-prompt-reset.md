# Briefing zespołu — 2026-08-04: safety prompt + reset migracji

## Co się zmienia

1. **Rozdział promptu persony**
   - User edytuje tylko **zachowanie** („Jak ma się zachowywać” / `system_prompt`).
   - **Lekarz / leki / red flags / „czego NIE robisz”** → `app_private.persona_template_safety` (niewidoczne w API/UI).
   - `persona_constraints` nadal systemowe (nie w DTO).

2. **Migracje**
   - Usunięto `0003_professional_templates.sql` (treść w `0001`).
   - Nowy wipe: `supabase/reset_public.sql` (ręcznie przed re-init).
   - Kolejność: wipe → `0001_init.sql` → `0002_exercise_catalog.sql`.
   - Docs: `cloud-setup.md` Krok 4 zaktualizowany.

3. **Backend**
   - `PREAMBLE_VERSION = 2`
   - Chat + plan doklejają safety przez `service_role_connection`
   - Spec: `docs/superpowers/specs/2026-08-04-persona-safety-prompt-design.md`

## Co zrobić lokalnie / na chmurze

1. Supabase SQL Editor: uruchom `reset_public.sql`
2. Uruchom `0001_init.sql`, potem `0002_exercise_catalog.sql`
3. Redeploy backend (Render) po merge — bez tego stare API bez safety
4. Smoke: dodaj dietetyka → w UI **nie** ma bloku o lekarzu/lekach; w zachowaniu jest styl/zakres pomocy

## Audyt (synteza zespołu)

Równolegle: [Architektura](9667dfc1-40ea-45ac-8e09-5428c667d0bf), [Security](71dd8db8-bb81-4933-b026-bbd2dbf2164e), [Code review](2f5c2f82-7f8e-4a18-bb54-d5a508163059), [UX](b4bba55d-fa89-4166-becd-5a8cdf5e1dc7).

| Finding | Status po wdrożeniu |
|---|---|
| Safety w edytowalnym `default_prompt` | ✅ rozdzielone w `0001` + `app_private` |
| PlanOrchestrator bez preambułu/safety | ✅ dokleja `build_system_prompt` + safety |
| PostgREST może UPDATE `persona_constraints` | ✅ trigger `guard_persona_constraints` |
| Clone kopiuje constraints | ✅ `None` przy clone |
| UX: „system prompt” / pełny seed z zakazami | ✅ „Styl i zakres pomocy” + hint warstwy |
| Pełne przeniesienie `persona_constraints` do `internal` (SELECT hide) | ⏳ backlog (Data API nadal widzi kolumnę na własnych wierszach) |
| Preview gotowca bez full-text wklejania | ⏳ backlog UX |

MCP Supabase w tej sesji **nie widzi** projektu o nazwie `goat` — wipe/init trzeba odpalić ręcznie w SQL Editor docelowego projektu.
