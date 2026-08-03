## Learned User Preferences

- Instrukcje setupu, migracji i deployu mają być konkretne, krok po kroku, z listami klucz→wartość w tabelkach — nie ogólne opisy.
- Aktualnie priorytet: setup **chmury** (Supabase + Render + Vercel + Cloudflare); local loop / lokalny Postgres to ścieżka na później.
- Przy większych tematach (architektura, plan, audyt) preferuje równoległy przegląd przez zespół ekspertów (subagenci) i zwięzłą syntezę decyzji.
- Po większych partiach pracy często prosi o aktualizację dokumentacji oraz push na `main` (po testach, gdy o to poprosi).
- Komunikacja i odpowiedzi agenta: po polsku.
- Nie wklejać prawdziwych sekretów do `.env.example`, commitów ani czatu — tylko placeholdery.

## Learned Workspace Facts

- Repo / produkt nazywa się **`goat`** (nie `coach-dev`); aplikacja to Multi-Persona Coaching App (max 5 person, czat, wyniki, plany).
- Stack: frontend Vite + React (Vercel), backend FastAPI (Render), Supabase Cloud (Postgres + Auth), OpenRouter, DNS Cloudflare.
- Domeny: `goat.fmazurkiewicz.dev` (FE), `api-goat.fmazurkiewicz.dev` (API).
- Monorepo: `backend/`, `frontend/`, `supabase/migrations/`, docs w `docs/` (`cloud-setup.md` = aktualny deploy).
- Migracje cloud: SQL Editor — przy re-init: `supabase/reset_public.sql` → `0001_init.sql` → `0002_exercise_catalog.sql` (bez 0003; safety w `app_private`).
- Prompt persony: user edytuje tylko zachowanie (`system_prompt`); lekarz/leki/red flags w `app_private.persona_template_safety` + preambuł; `persona_constraints` systemowe (nie w API Out).
- Spec decyzji: `docs/superpowers/specs/2026-08-04-persona-safety-prompt-design.md`; briefing: `docs/team/2026-08-04-safety-prompt-reset.md`.
- Interaktywne makiety UI: `D:\Nasze\ślub\Pięć ekranów aplikacji`.
- Na Render `DATABASE_URL` musi iść przez Supabase Connection pooler (Supavisor, port 6543); bezpośredni `db.<ref>.supabase.co` daje `Network is unreachable` (IPv6).
- Cloudflare CNAME dla `goat` / `api-goat`: Proxy status = DNS only (szara chmura); w polach Name/Target bez `https://`.
- Root `.gitignore` nie może mieć gołego `lib/` — tylko `/lib/`, inaczej `frontend/src/lib/` wypada z gita/Vercela.
