# Uruchomienie lokalne

**Aktualnie setupujemy chmurę** — pełna ścieżka: [`cloud-setup.md`](cloud-setup.md) (projekt Supabase **`goat`**).

Ten dokument: lokalny loop (backend/frontend na maszynie + ten sam projekt Supabase `goat`, albo w przyszłości lokalny Postgres). Bez Dockera.

---

## A. Supabase — ten sam projekt `goat` (już z cloud-setup)

Jeśli projekt `goat` i migracje są już w chmurze, **nie twórz drugiego projektu**. Użyj tych samych kluczy / poolera z [`cloud-setup.md`](cloud-setup.md) §1.4.

Gdybyś startował od zera tylko lokalnie (bez deployu):

### A1. Projekt

1. [supabase.com](https://supabase.com) → **New project**.
2. Name: **`goat`** (nie `coach-dev`).
3. Database password: **wygeneruj i zapisz**.
4. Region: np. **Frankfurt**.
5. Active → zapisz **Reference ID** (`<ref>`).

### A2. Google OAuth (Google Cloud + Supabase)

**Google Cloud Console** ([console.cloud.google.com](https://console.cloud.google.com)):

1. Utwórz / wybierz projekt GCP.
2. APIs & Services → **OAuth consent screen** → External → wypełnij nazwę apki, swój email → Save.
3. APIs & Services → **Credentials** → Create credentials → **OAuth client ID** → Application type: **Web application**.
4. Authorized JavaScript origins: `http://localhost:3000`
5. Authorized redirect URIs:  
   `https://<ref>.supabase.co/auth/v1/callback`
6. Create → skopiuj **Client ID** i **Client Secret**.

**Supabase Dashboard:**

1. Authentication → **Providers** → **Google** → Enable.
2. Wklej Client ID i Client Secret → Save.
3. Authentication → **URL Configuration** — do local dodaj obok prod:
   - Redirect URLs: `http://localhost:3000/**` (Site URL może zostać `https://goat.fmazurkiewicz.dev`).

### A3. Migracje (SQL Editor — bez CLI)

1. W repo otwórz pliki:
   - `supabase/migrations/0001_init.sql`
   - `supabase/migrations/0002_exercise_catalog.sql`
2. Supabase → **SQL** → **New query**.
3. Wklej **całą** treść `0001_init.sql` → **Run** (musi przejść bez błędu).
4. Nowa query → wklej **całą** treść `0002_exercise_catalog.sql` → **Run**.
5. Kolejne migracje (jeśli jeszcze nie były na projekcie): `0007_running_metrics_strength.sql`, `0008_background_jobs.sql`, `0009_persona_role_boundaries.sql`, `0010_drop_personas_chat_model.sql`, `0011_invoked_via_multi_slash.sql`, `0012_exercise_catalog_source_nullable.sql`, `0013_exercise_catalog_seed_free_exercise_db.sql` — każda w osobnej query, **Run**. `0013` jest duży (~1 MB) i wygenerowany — patrz niżej „Import katalogu ćwiczeń".
6. **Table Editor** — powinny być m.in.:
   - `profiles`, `personas`, `persona_templates`, `plan_templates`, `allowed_metrics`
   - `chat_sessions`, `chat_messages`, `results`, `plans`, `plan_items`
   - `usage_limits`, `exercises`, `background_jobs`
7. Sprawdź seed: `persona_templates` i `exercises` mają wiersze.

### A4. Skopiuj connection string i klucze

**Database** (Project Settings → Database):

1. Connection string → **URI**.
2. Wybierz **Connection pooling** (Supavisor), mode **Transaction**, port **6543**.
3. Skopiuj URI i podmień `[YOUR-PASSWORD]` na hasło z A1.  
   Przykładowy kształt (host/region mogą się różnić — bierz z UI):

```text
postgresql://postgres.<ref>:<HASLO>@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
```

Dla backendu dodaj dialect: `postgresql+asyncpg://...` (zamień prefiks `postgresql://` na `postgresql+asyncpg://`).

**API** (Project Settings → API):

| Pole w panelu | Gdzie wstawisz |
|---|---|
| Project URL | `SUPABASE_URL`, `VITE_SUPABASE_URL` |
| `anon` `public` | `VITE_SUPABASE_ANON_KEY` |
| `service_role` `secret` | `SUPABASE_SERVICE_ROLE_KEY` (tylko backend!) |

JWKS (stały wzorzec):

```text
https://<ref>.supabase.co/auth/v1/.well-known/jwks.json
```

---

## B. OpenRouter (LLM)

1. [openrouter.ai](https://openrouter.ai) → konto → API Keys → Create key.
2. Zapisz klucz (pójdzie do `OPENROUTER_API_KEY` w backendzie).
3. Opcjonalnie: ustaw soft limit wydatków + alert mailowy.

---

## C. Pliki env (lokalnie, nie commitować)

Lokalnie: **Postgres na localhost** + **login email/hasło** (bez Supabase OAuth).  
Render/Vercel: **OAuth Google** + Supabase JWKS (bez dev login).

### C1. Backend

```powershell
cd C:\Users\MSI\PycharmProjects\goat\backend
copy .env.example .env
```

Edytuj `backend/.env`:

```env
ENVIRONMENT=local

DATABASE_URL=postgresql+asyncpg://postgres:<HASLO>@localhost:5432/goat

DEV_AUTH_EMAIL=<twoj-email>
DEV_AUTH_PASSWORD=<twoje-haslo>
DEV_AUTH_USER_ID=00000000-0000-4000-8000-000000000001
LOCAL_JWT_SECRET=<losowy-ciag>

OPENROUTER_API_KEY=<klucz z OpenRouter>
OPENROUTER_CHAT_MODEL=anthropic/claude-haiku-4.5
OPENROUTER_PLANNER_MODEL=anthropic/claude-sonnet-4.6

CORS_ORIGINS=http://localhost:3000
```

`SUPABASE_*` **nie są wymagane lokalnie** — zostaw zakomentowane / puste.

### C2. Frontend

```powershell
cd C:\Users\MSI\PycharmProjects\goat\frontend
copy .env.example .env.local
```

Edytuj `frontend/.env.local`:

```env
VITE_ENABLE_DEV_LOGIN=true
VITE_API_BASE_URL=http://localhost:8000
```

`VITE_SUPABASE_*` **nie są wymagane lokalnie** przy `VITE_ENABLE_DEV_LOGIN=true`.

Nigdy nie commituj `.env` / `.env.local` i nie wklejaj sekretów do czatu.

---

## D. Uruchomienie procesów

### D1. Backend (terminal 1)

```powershell
cd C:\Users\MSI\PycharmProjects\goat\backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### D2. Frontend (terminal 2)

```powershell
cd C:\Users\MSI\PycharmProjects\goat\frontend
npm install
npm run dev
```

Frontend: `http://localhost:3000`  
API: `http://localhost:8000`

---

## E. Smoke test

1. `curl http://localhost:8000/api/health` → `200` / `{"status":"ok"}` (lub równoważne).
2. Przeglądarka → `http://localhost:3000` → **Zaloguj się** (email/hasło z `DEV_AUTH_*`).
3. Utwórz personę z szablonu.
4. **Ogólna rozmowa** → „Generuj zharmonizowany plan na sierpień” → **Goat · Kierownik Zespołu** (nie dietetyk); wynik w zakładce Plany.
5. (Opcjonalnie) wygeneruj plan tygodniowy → status joba `success` / `partial_success`.
6. Sprawdź `/results` i `/settings`.

---

## E2. Import katalogu ćwiczeń (free-exercise-db)

Katalog seedowany jest migracją **`0013`** (wygenerowanym plikiem w repo — nie uruchamiaj importu, żeby mieć dane). Skrypt regenerujesz tylko przy aktualizacji datasetu:

```powershell
# 1. Pobierz dataset + wygeneruj 0013 (bez sekretów, bez bazy)
cd backend; uv run python ../scripts/import_free_exercise_db.py

# 2. (opcjonalnie) Tłumaczenia PL przez LLM — wymaga prawdziwego OPENROUTER_API_KEY
uv run python ../scripts/translate_exercises.py        # cache: .tmp/free-exercise-db-translations.json
uv run python ../scripts/import_free_exercise_db.py    # regeneracja 0013 z PL

# 3. (opcjonalnie) Zdjęcia do Supabase Storage — wymaga SUPABASE_URL + SERVICE_ROLE_KEY
uv run python ../scripts/import_free_exercise_db.py --upload-photos
```

Po regeneracji: commit `0013_*.sql`, potem Run w SQL Editor (lokalnie i na cloudzie).
Re-import istniejących danych: `DELETE FROM exercises WHERE source='free_exercise_db';` → rerun `0013`.

---

## F. Na później — lokalny Postgres zamiast Supabase DB

Gdy zechcesz `DATABASE_URL` na `localhost` (Auth może zostać w Supabase Cloud):

1. Postgres 16 lokalnie → `CREATE DATABASE goat;`
2. Stub `auth` (jak w CI `.github/workflows/ci.yml`) — `pgcrypto` + `auth.users` + `auth.uid()`.
3. **Rola `service_role` (NOLOGIN)** — w Supabase istnieje od razu, w czystym Postgresie nie; bez niej `app/main.py:lifespan` pada na `SET LOCAL ROLE service_role` (`role "service_role" does not exist`). Migracja `0001` jej **nie** tworzy (używa tylko w `GRANT`ach).
4. `psql -f supabase/migrations/0001_init.sql` potem `0002_exercise_catalog.sql` i kolejne (`0007`–`0011`).
5. `DATABASE_URL=postgresql+asyncpg://postgres:...@localhost:5432/goat`
6. Po pierwszym Google login wstaw UUID z JWT (`sub`) do lokalnego `auth.users` (FK).

Kroki 2-3 (bootstrap przed migracjami, `psql`):

```sql
create extension if not exists pgcrypto;
create schema if not exists auth;
create table if not exists auth.users (
  id uuid primary key default gen_random_uuid(),
  email text
);
-- Odwzorowanie auth.uid() z Supabase, żeby polityki RLS dały się utworzyć lokalnie.
create or replace function auth.uid() returns uuid as $$
  select nullif(current_setting('request.jwt.claims', true)::json->>'sub', '')::uuid
$$ language sql stable;
-- Wymagane przez backend (SET LOCAL ROLE) i GRANT-y w migracjach.
create role service_role nologin;
```

Szczegóły nie są potrzebne przy pierwszym setupie — wróć tu dopiero gdy świadomie przełączysz DB.

---

## G. Graft — mapa kodu dla agenta (ADR-20)

Lokalny graf kontekstu ([NanoNets/Graft](https://github.com/nanonets/graft)). **Nie jest częścią runtime** — nie trzeba go do `uvicorn` / `npm run dev` / deployu. Agent używa go zamiast ślepego grepa.

### G1. Pierwszy raz (ta maszyna / to repo)

```powershell
npx @nanonets/graft init --agents cursor --dry-run
npx @nanonets/graft init --agents cursor
npx @nanonets/graft telemetry disable
npx @nanonets/graft build
```

`init --agents cursor` zapisuje tylko:

| Plik | Commitować? |
|---|---|
| `.cursor/rules/graft.mdc` | tak (wiring) |
| `.cursor/mcp.json` | tak (MCP, bez sekretów) |
| `graft/` | **nie** — cache; `graft build` dopisuje `/graft/` do `.gitignore` |

Restart Cursora, żeby MCP się załadował.

### G2. Kiedy `graft build`

| Kiedy | Komenda |
|---|---|
| Start sesji, gdy graf odstaje od kodu | `npx @nanonets/graft check` → przy exit 1: `npx @nanonets/graft build` |
| Po merżu / dużym refaktorze / wielu plikach | `npx @nanonets/graft build` |
| `ask` / `callers` wyglądają nieaktualnie | `npx @nanonets/graft build` |

Nie po każdej linijce — zwykłe odpytania odświeżają strukturę same (~3 ms, $0).

### G3. Opcjonalnie `--deep` (LLM)

Tylko świadomie. Klucz **lokalnie** (nie w czacie, nie w commicie). Placeholdery:

| Zmienna | Przykład |
|---|---|
| `GRAFT_PROVIDER` | `openai` (wire format OpenAI-compatible) |
| `GRAFT_BASE_URL` | `https://openrouter.ai/api/v1` |
| `GRAFT_API_KEY` | ustaw lokalnie |
| `GRAFT_MODEL` | model z OpenRoutera |

Potem: `npx @nanonets/graft build --deep`.

---

## Checklist (pierwszy raz)

| # | Krok | OK? |
|---|---|---|
| 1 | Projekt Supabase **`goat`** Active (zwykle już z cloud-setup) | |
| 2 | Google OAuth w GCP + Supabase Providers | |
| 3 | Site URL / Redirect `localhost:3000` | |
| 4 | SQL: `0001_init` + `0002` + `0007`–`0011` jeśli brak | |
| 5 | Table Editor: tabele + seed | |
| 6 | OpenRouter API key | |
| 7 | `backend/.env`: localhost + `DEV_AUTH_*` (bez Supabase) | |
| 8 | `frontend/.env.local`: `VITE_ENABLE_DEV_LOGIN=true` | |
| 9 | `uv run uvicorn` na :8000 | |
| 10 | `npm run dev` na :3000 | |
| 11 | Health + login email/hasło + persona + czat | |
| 12 | (opcjonalnie, tooling) Graft: `init --agents cursor` + `telemetry disable` + `build` — §G | |
