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
5. Kolejne migracje (jeśli jeszcze nie były na projekcie): `0007_running_metrics_strength.sql`, `0008_background_jobs.sql` — każda w osobnej query, **Run**.
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
4. Wyślij wiadomość w czacie → streaming tokenów (SSE).
5. (Opcjonalnie) wygeneruj plan tygodniowy → status joba `success` / `partial_success`.
6. Sprawdź `/results` i `/settings`.

---

## F. Na później — lokalny Postgres zamiast Supabase DB

Gdy zechcesz `DATABASE_URL` na `localhost` (Auth może zostać w Supabase Cloud):

1. Postgres 16 lokalnie → `CREATE DATABASE coach_dev;`
2. Stub `auth` (jak w CI `.github/workflows/ci.yml`) — `pgcrypto` + `auth.users` + `auth.uid()`.
3. `psql -f supabase/migrations/0001_init.sql` potem `0002_exercise_catalog.sql`.
4. `DATABASE_URL=postgresql+asyncpg://postgres:...@localhost:5432/coach_dev`
5. Po pierwszym Google login wstaw UUID z JWT (`sub`) do lokalnego `auth.users` (FK).

Szczegóły nie są potrzebne przy pierwszym setupie — wróć tu dopiero gdy świadomie przełączysz DB.

---

## Checklist (pierwszy raz)

| # | Krok | OK? |
|---|---|---|
| 1 | Projekt Supabase **`goat`** Active (zwykle już z cloud-setup) | |
| 2 | Google OAuth w GCP + Supabase Providers | |
| 3 | Site URL / Redirect `localhost:3000` | |
| 4 | SQL: `0001_init` + `0002_exercise_catalog` (+ `0007`, `0008` jeśli brak) | |
| 5 | Table Editor: tabele + seed | |
| 6 | OpenRouter API key | |
| 7 | `backend/.env`: localhost + `DEV_AUTH_*` (bez Supabase) | |
| 8 | `frontend/.env.local`: `VITE_ENABLE_DEV_LOGIN=true` | |
| 9 | `uv run uvicorn` na :8000 | |
| 10 | `npm run dev` na :3000 | |
| 11 | Health + login email/hasło + persona + czat | |
