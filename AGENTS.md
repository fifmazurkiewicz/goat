## Learned User Preferences

- Instrukcje setupu, migracji i deployu mają być konkretne, krok po kroku, z listami klucz→wartość w tabelkach — nie ogólne opisy.
- Deploy/prod: chmura (Supabase + Render + Vercel + Cloudflare); lokalnie: backend + frontend + Postgres na localhost (baza `goat`); auth lokalnie email/hasło (dev), na Render/produkcji tylko OAuth.
- Przy większych tematach (architektura, plan, audyt) preferuje równoległy przegląd przez zespół ekspertów (subagenci) i zwięzłą syntezę decyzji.
- Po większych partiach pracy często prosi o aktualizację dokumentacji oraz push na `main` (po testach, gdy o to poprosi).
- Komunikacja i odpowiedzi agenta: po polsku.
- Nie wklejać prawdziwych sekretów do `.env.example`, commitów ani czatu — tylko placeholdery.
- Wybór gotowca persony: lista rozwijana (`Select`), nie siatka buttonów/radio.
- Klik w brand/nazwę „Coach” w nawigacji wraca do ekranu chatu; zakładka Profil usunięta — nick w ustawieniach konta.
- Domyślne/seed wyniki mają zależeć od person użytkownika, nie od uniwersalnych hardcoded sportów (np. badminton/triathlon dla każdego).
- Usuwanie persony: z dialogu edycji (nie tylko z karty na liście).
- W czacie (Ogólna rozmowa): user komunikuje się **tylko z Goat**; trenerzy za kulisami, Goat przekazuje odpowiedzi; bezpośrednio z personą wyłącznie przez `/slug`; roundtable („niech każdy”) → N wiadomości Goata (wszyscy aktywni trenerzy). Status „Goat + akcja”; Markdown (`remark-gfm`/`remark-breaks`, preambuła v7); dedup etykiety gdy imię=rola; chipy tooli zamiast JSON; pole Wyślij w viewport; tytuły rozmów auto + edycja PPM.
- Persony mają układać plany i zapisywać wyniki (zakładki Plan/Wyniki); plan ma być uzgodniony ze wszystkimi aktywnymi personami (edycja + przebudowa), nie tylko rekomendacja w czacie.

## Learned Workspace Facts

- Repo / produkt nazywa się **`goat`** (nie `coach-dev`); aplikacja to Multi-Persona Coaching App (max 5 person, czat, wyniki, plany).
- Stack: frontend Vite + React (Vercel), backend FastAPI (Render), Supabase Cloud (Postgres + Auth), OpenRouter, DNS Cloudflare.
- Domeny: `goat.fmazurkiewicz.dev` (FE), `api-goat.fmazurkiewicz.dev` (API); prod Supabase project id: `dynkfllyfykudfxymmtc`.
- Monorepo: `backend/`, `frontend/`, `supabase/migrations/`, docs w `docs/` (`cloud-setup.md` = aktualny deploy).
- Migracje cloud: SQL Editor — re-init: `supabase/reset_public.sql` → `0001_init.sql` → `0002_exercise_catalog.sql` (bez 0003; safety w `app_private`); bieganie pod motorykę: `0007_running_metrics_strength.sql`; role boundaries: `0009_persona_role_boundaries.sql`; drop `chat_model`: `0010_drop_personas_chat_model.sql`; multi-slash invoked_via: `0011_invoked_via_multi_slash.sql`.
- **Goat (Kierownik Zespołu):** w sesji `general` user rozmawia **wyłącznie z Goat**; trenerzy konsultowani za kulisami, Goat przekazuje odpowiedzi (`format_goat_relay`); bezpośrednio z personą tylko `/slug`; przy planie — `rebuild_plan`; docs: `docs/technical/team-lead.md`, ADR-17.
- `motor_coach` → kategoria wyników `strength` (UI: zakładka Trening); bez osobnej kategorii `running`/`cardio`.
- Prompt persony: user edytuje tylko zachowanie (`system_prompt`); lekarz/leki/red flags w `app_private.persona_template_safety` + preambuł; w prompcie czatu data dnia (Europe/Warsaw); modele LLM (chat/planner/personas) z env OpenRouter, nie kolumna w DB (`0010_drop_personas_chat_model.sql`).
- Vercel SPA: `frontend/vercel.json` z rewrite `/(.*) → /index.html` — bez tego odświeżenie `/personas`, `/settings` itd. daje `404` na CDN.
- Na Render `DATABASE_URL` musi iść przez Supabase Connection pooler (Supavisor, port 6543); bezpośredni `db.<ref>.supabase.co` daje `Network is unreachable` (IPv6); lokalnie: `postgresql+asyncpg://…@localhost:5432/goat` (bez poolera).
- Cloudflare CNAME dla `goat` / `api-goat`: Proxy status = DNS only (szara chmura); w polach Name/Target bez `https://`.
- Jedyny admin: `fmazurkiewicz@gmail.com` (allowlist); `/account` = nick (ADR-15), `/profile` = biometria; panel admin: Moderacja i Log audytowy w zwiniętej „Diagnostyka platformy”; `ProfilesRepo.ensure()` przed zapisem; asyncpg: UUID→str w DTO, jsonb przez `CAST(:param AS jsonb)`.
- Chat tools: `log_result`, `update_user_profile`, `get_plan`, `upsert_plan_items`; **`rebuild_plan` tylko Goat**; general bez slashy: trenerzy backstage + `format_goat_relay`; slash/multi-slash: persona widoczna w UI; roundtable `user_requests_all_trainers` → wszyscy aktywni; preambuła v7; SSE statusy PL; layout: AppShell `h-svh`, scroll w MessageList.
