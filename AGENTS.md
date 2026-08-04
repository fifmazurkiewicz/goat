## Learned User Preferences

- Instrukcje setupu, migracji i deployu mają być konkretne, krok po kroku, z listami klucz→wartość w tabelkach — nie ogólne opisy.
- Aktualnie priorytet: setup **chmury** (Supabase + Render + Vercel + Cloudflare); local loop / lokalny Postgres to ścieżka na później.
- Przy większych tematach (architektura, plan, audyt) preferuje równoległy przegląd przez zespół ekspertów (subagenci) i zwięzłą syntezę decyzji.
- Po większych partiach pracy często prosi o aktualizację dokumentacji oraz push na `main` (po testach, gdy o to poprosi).
- Komunikacja i odpowiedzi agenta: po polsku.
- Nie wklejać prawdziwych sekretów do `.env.example`, commitów ani czatu — tylko placeholdery.
- Wybór gotowca persony: lista rozwijana (`Select`), nie siatka buttonów/radio.
- Klik w brand/nazwę „Coach” w nawigacji wraca do ekranu chatu; zakładka Profil usunięta — nick w ustawieniach konta.
- Domyślne/seed wyniki mają zależeć od person użytkownika, nie od uniwersalnych hardcoded sportów (np. badminton/triathlon dla każdego).
- Usuwanie persony: z dialogu edycji (nie tylko z karty na liście).
- W czacie: status „persona + akcja po ludzku” (jedna linia, znika przy pierwszym tokenie); Markdown zamiast surowych `**`; bez logów/`role=tool` JSON (chipy tooli: czytelne summary); pole Wyślij zawsze w viewport bez scrolla strony; OK kilka wiadomości od trenerów przy uzgadnianiu planu.
- Persony mają układać plany i zapisywać wyniki (zakładki Plan/Wyniki); plan ma być uzgodniony ze wszystkimi aktywnymi personami (edycja + przebudowa), nie tylko rekomendacja w czacie.

## Learned Workspace Facts

- Repo / produkt nazywa się **`goat`** (nie `coach-dev`); aplikacja to Multi-Persona Coaching App (max 5 person, czat, wyniki, plany).
- Stack: frontend Vite + React (Vercel), backend FastAPI (Render), Supabase Cloud (Postgres + Auth), OpenRouter, DNS Cloudflare.
- Domeny: `goat.fmazurkiewicz.dev` (FE), `api-goat.fmazurkiewicz.dev` (API); prod Supabase project id: `dynkfllyfykudfxymmtc`.
- Monorepo: `backend/`, `frontend/`, `supabase/migrations/`, docs w `docs/` (`cloud-setup.md` = aktualny deploy).
- Migracje cloud: SQL Editor — re-init: `supabase/reset_public.sql` → `0001_init.sql` → `0002_exercise_catalog.sql` (bez 0003; safety w `app_private`); bieganie pod motorykę: `0007_running_metrics_strength.sql` (`strength`).
- `motor_coach` → kategoria wyników `strength` (UI: zakładka Trening); bez osobnej kategorii `running`/`cardio`.
- Prompt persony: user edytuje tylko zachowanie (`system_prompt`); lekarz/leki/red flags w `app_private.persona_template_safety` + preambuł; w prompcie czatu data dnia (Europe/Warsaw).
- Vercel SPA: `frontend/vercel.json` z rewrite `/(.*) → /index.html` — bez tego odświeżenie `/personas`, `/settings` itd. daje `404` na CDN.
- Na Render `DATABASE_URL` musi iść przez Supabase Connection pooler (Supavisor, port 6543); bezpośredni `db.<ref>.supabase.co` daje `Network is unreachable` (IPv6).
- Cloudflare CNAME dla `goat` / `api-goat`: Proxy status = DNS only (szara chmura); w polach Name/Target bez `https://`.
- Jedyny admin: `fmazurkiewicz@gmail.com` (allowlist); `/account` = nick (ADR-15), `/profile` = biometria; `ProfilesRepo.ensure()` przed zapisem; asyncpg: UUID→str w DTO, jsonb przez `CAST(:param AS jsonb)`.
- Chat tools dziś: `log_result`, `update_user_profile`; brak toola Planów (pipeline `/plans`, 3 etapy); SSE już emituje `persona_turn_start`/`tool_call_start` — statusy PL mapowane na FE; layout czatu: AppShell `h-svh`, scroll tylko w MessageList.
