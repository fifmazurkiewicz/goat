# Setup chmury — projekt `goat` (szczegółowo)

Kolejność ma znaczenie: **Supabase → OpenRouter → Render → Vercel → Cloudflare → domknięcie**.

| Warstwa | Host |
|---|---|
| Frontend | `goat.fmazurkiewicz.dev` |
| API | `api-goat.fmazurkiewicz.dev` |

Nazwa projektu: **`goat`**. Lokalny loop: [`local-setup.md`](local-setup.md) — później.

Trzymaj w notatniku (nie w repo / nie w czacie z sekretami):

- hasło bazy Supabase
- Reference ID (`<ref>`)
- Project URL, `anon` key, `service_role` key
- connection string poolera
- OpenRouter API key
- URL serwisu Render (`*.onrender.com`)

---

## Krok 1 — Supabase: utworzenie projektu

1. Wejdź na [https://supabase.com](https://supabase.com) i zaloguj się.
2. Kliknij **New project** (albo **Start a new project**).
3. Wybierz organizację (lub utwórz nową).
4. W formularzu:
   - **Name:** `goat` (dokładnie tak — nie `coach`, nie `coach-dev`).
   - **Database Password:** kliknij Generate password albo wpisz własne. **Skopiuj i zapisz od razu** — później nie zobaczysz go w jasnej postaci.
   - **Region:** wybierz najbliższy, preferowane **Frankfurt (eu-central-1)** albo West EU.
   - Pricing: Free (wystarczy na start).
5. Kliknij **Create new project**.
6. Poczekaj 1–2 minuty aż status projektu będzie zielony / **Active** (nie Provisional / Setting up).
7. W lewym menu dolnym (ikona zębatki) → **Project Settings** → zakładka **General**.
8. Skopiuj **Reference ID** — krótki ciąg typu `abcdefghijklmnopqrst`. To jest Twoje `<ref>`.
9. Zapisz też **Project URL** z tej strony / z API — zwykle `https://<ref>.supabase.co`.

---

## Krok 2 — Google Cloud: klient OAuth

Bez tego przycisk „Zaloguj przez Google” w aplikacji nie zadziała.

1. Wejdź na [https://console.cloud.google.com](https://console.cloud.google.com).
2. U góry wybierz istniejący projekt GCP albo **New Project**:
   - Nazwa projektu GCP może być `goat` (to osobna nazwa od Supabase — może być taka sama).
   - Create → poczekaj → wybierz ten projekt w selektorze.
3. W menu (☰) → **APIs & Services** → **OAuth consent screen**.
   - Jeśli Google pokazuje nowy flow „Google Auth Platform” / Branding — wejdź w konfigurację ekranu zgody.
4. User type: **External** → Create.
5. Wypełnij minimum:
   - App name: `goat`
   - User support email: Twój email
   - Developer contact: Twój email
   - Save and Continue przez Scopes (możesz nic nie dodawać na MVP) → Test users (opcjonalnie dodaj siebie, jeśli app jest w Testing) → Back to Dashboard.
6. **APIs & Services** → **Credentials** → **+ Create credentials** → **OAuth client ID**.
7. Application type: **Web application**.
8. Name: np. `goat-web`.
9. **Authorized JavaScript origins** → Add URI:
   - `https://goat.fmazurkiewicz.dev`
   - (później local) `http://localhost:3000`
10. **Authorized redirect URIs** → Add URI:
    - `https://<ref>.supabase.co/auth/v1/callback`  
      (wstaw swoje `<ref>` z Kroku 1 — bez spacji, z `https://`)
11. Kliknij **Create**.
12. W oknie pojawią się **Client ID** i **Client Secret** — skopiuj oba i zapisz.  
    (Secret później: Credentials → kliknij klienta → Client secrets.)

---

## Krok 3 — Supabase: włączenie Google + URL-e

1. Wróć do Dashboard projektu **goat** na Supabase.
2. Lewe menu → **Authentication** → **Providers**.
3. Znajdź **Google** → kliknij wiersz / Edit.
4. Przełącz **Enable Sign in with Google** na włączony.
5. Wklej:
   - **Client ID** z Google Cloud
   - **Client Secret (for OAuth)** z Google Cloud
6. **Save**.
7. Nadal w Authentication → **URL Configuration** (czasem pod **Authentication → Settings**).
8. Ustaw:
   - **Site URL:** `https://goat.fmazurkiewicz.dev`
   - **Redirect URLs:** kliknij Add / w polu listy dodaj dokładnie:
     - `https://goat.fmazurkiewicz.dev/**`
9. **Save**.  
   (Gdy domena jeszcze nie działa, Site URL możesz tymczasowo ustawić na URL z Vercel `https://….vercel.app` i dodać go też do Redirect URLs — potem wróć do `goat.fmazurkiewicz.dev`.)

---

## Krok 4 — Supabase: reset (opcjonalnie) + migracje w SQL Editor

Jeśli baza ma stare tabele / połowiczny seed — **najpierw wipe**, potem świeży init.

### 4a. Wipe (gdy resetujesz środowisko)

1. Otwórz `supabase/reset_public.sql`.
2. Supabase → **SQL** → **SQL Editor** → New query → wklej całość → **Run**.
3. Potwierdź sukces. Kasuje tabele w `public` + schemat `app_private` (dane aplikacyjne). Konta `auth.users` zostają.
4. Jeśli używasz CLI `supabase db push`: wyczyść też `supabase_migrations.schema_migrations` (komentarz w pliku wipe).

### 4b. Init

1. Na dysku:
   - `supabase/migrations/0001_init.sql` (schemat + seed zachowania + `app_private` safety)
   - `supabase/migrations/0002_exercise_catalog.sql`
2. SQL Editor → New query → wklej **całą** treść `0001_init.sql` → **Run**.
3. New query → wklej **całą** treść `0002_exercise_catalog.sql` → **Run**.
4. (Istniejące DB bez wipe) New query → `0007_running_metrics_strength.sql` → **Run**
   (metryki biegania pod `strength` / zakładka Trening; przy świeżym `0001_init` już w seedzie).
5. **Obowiązkowo przed deployem backendu z `main` (2026-08-04+):** New query →
   `0008_background_jobs.sql` → **Run** — bez tego API startuje, ale joby w tle (tytuły LLM,
   harmonizacja po upsert) nie działają; po poprawce startupu brak migracji nie blokuje health.
6. Table Editor — powinny być m.in.:
   - `profiles`, `personas`, `persona_templates`, `plan_templates`, `allowed_metrics`
   - `user_profile`, `chat_sessions`, `chat_messages`, `results`
   - `plans`, `plan_items`, `plan_generation_jobs`, `plan_generation_job_personas`
   - `usage_limits`, `moderation_events`, `admin_audit_log`, `exercises`
5. `persona_templates` — wiersze z profesjonalnym `default_prompt` (bez bloku „Czego NIE robisz”).
6. Schemat `app_private` / tabela `persona_template_safety` — widoczna dla roli serwisowej; **nie** przez zwykły Table Editor jako `authenticated` (to zamierzone).

Nie ma już pliku `0003_professional_templates.sql` — treści są w `0001`.

---

## Krok 5 — Supabase: connection string i klucze API

### 5a. Connection string (pod Render / `DATABASE_URL`)

1. Project Settings (zębatka) → **Database**.
2. Sekcja **Connection string** (lub Connect → ORMs / Connection pooling — UI się zmienia).
3. Wybierz:
   - typ: **URI**
   - metoda: **Connection pooling** / **Pooler**
   - mode: **Transaction**
   - port: **6543** (nie 5432)
4. Skopiuj string. Wygląda mniej więcej tak:

```text
postgresql://postgres.<ref>:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
```

Host (`aws-0-….pooler.supabase.com`) **weź dokładnie z panelu** — nie zgaduj regionu.
5. Zamień `[YOUR-PASSWORD]` na hasło z Kroku 1. Jeśli hasło ma znaki specjalne (`@`, `#`, `%`…), muszą być **URL-encoded** (np. `@` → `%40`).
6. Na potrzeby backendu zmień początek:
   - z: `postgresql://`
   - na: `postgresql+asyncpg://`  
   To będzie wartość `DATABASE_URL`.

### 5b. Klucze API

1. Project Settings → **API**.
2. Skopiuj i zapisz:
   - **Project URL** → `https://<ref>.supabase.co` = `SUPABASE_URL` / `VITE_SUPABASE_URL`
   - **anon** `public` key (długi JWT) → `VITE_SUPABASE_ANON_KEY` (tylko frontend / Vercel)
   - **service_role** `secret` key → `SUPABASE_SERVICE_ROLE_KEY` (**tylko** Render; nigdy do Vercel / frontu / repo)
3. JWKS (stały wzorzec — nic nie kopiujesz z panelu, budujesz z `<ref>`):

```text
https://<ref>.supabase.co/auth/v1/.well-known/jwks.json
```

To jest `SUPABASE_JWKS_URL`.

---

## Krok 6 — OpenRouter

1. Wejdź na [https://openrouter.ai](https://openrouter.ai) → zaloguj / zarejestruj.
2. Menu → **Keys** (lub Settings → Keys).
3. **Create Key** → nazwa np. `goat-prod` → Create.
4. Skopiuj klucz od razu (`sk-or-…`) → to `OPENROUTER_API_KEY`.
5. Zalecane: Settings / Credits → ustaw **soft limit** miesięczny + alert email, żeby nie przejechać budżetu.

---

## Krok 7 — Render: Web Service (backend)

### 7a. Utworzenie serwisu

1. Wejdź na [https://dashboard.render.com](https://dashboard.render.com) → zaloguj (najlepiej tym samym GitHubem co repo).
2. **New +** → **Web Service**.
3. Podłącz repozytorium **`fifmazurkiewicz/goat`** (Authorize GitHub jeśli trzeba) → Connect.
4. Wypełnij formularz:

| Pole | Wartość |
|---|---|
| Name | `goat-api` |
| Language / Runtime | **Docker** |
| Branch | `main` |
| Region | **Frankfurt** (jeśli dostępne; inaczej najbliższy EU) |
| Root Directory | `backend` |
| Dockerfile Path | `./Dockerfile` (względem Root Directory — czyli `backend/Dockerfile`) |
| Instance type | **Free** |

5. **Health Check Path:** `/api/health` (Advanced / Health — zależnie od UI).
6. **Auto-Deploy:** Yes (deploy przy pushu do `main`).

### 7b. Zmienne środowiskowe (przed pierwszym Deploy)

W sekcji **Environment** dodaj po jednej (klucz = wartość), **bez** cudzysłowów:

| Key | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | string z Kroku 5a (`postgresql+asyncpg://…`) |
| `SUPABASE_URL` | `https://<ref>.supabase.co` |
| `SUPABASE_JWKS_URL` | `https://<ref>.supabase.co/auth/v1/.well-known/jwks.json` |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role z Kroku 5b |
| `OPENROUTER_API_KEY` | klucz z Kroku 6 |
| `OPENROUTER_CHAT_MODEL` | `anthropic/claude-haiku-4.5` |
| `OPENROUTER_PLANNER_MODEL` | `anthropic/claude-sonnet-4.6` |
| `CORS_ORIGINS` | `https://goat.fmazurkiewicz.dev` |

Na start, zanim DNS zadziała, możesz tymczasowo ustawić:

```text
CORS_ORIGINS=https://goat.fmazurkiewicz.dev,https://TWOJ-PROJEKT.vercel.app
```

(Regex `*.vercel.app` i tak jest w kodzie backendu — ale jawna domena w `CORS_ORIGINS` nie zaszkodzi.)

### 7c. Deploy i weryfikacja

1. Kliknij **Create Web Service** / **Deploy**.
2. Otwórz zakładkę **Logs** — poczekaj aż build Docker przejdzie i pojawi się start uvicorn.
3. Skopiuj publiczny URL serwisu, np. `https://goat-api.onrender.com` (dokładną nazwę bierzesz z panelu).
4. W przeglądarce lub PowerShell:

```powershell
curl https://goat-api.onrender.com/api/health
```

Oczekiwane: HTTP 200 i JSON ze statusem OK (Free tier: pierwsze odpalenie może trwać 30–60 s — cold start).
5. **Custom Domain** na Render zostaw na Krok 10 (po Cloudflare).

---

## Krok 8 — Vercel: frontend

### 8a. Import projektu

1. Wejdź na [https://vercel.com](https://vercel.com) → zaloguj (GitHub).
2. **Add New…** → **Project** → wybierz repo **`goat`**.
3. Configure:
   - **Framework Preset:** Vite
   - **Root Directory:** kliknij Edit → wybierz folder **`frontend`** → Continue
   - Build Command: `npm run build` (domyślne Vite)
   - Output Directory: `dist`
   - Install Command: `npm install`
4. **Environment Variables** — dodaj dla Environment: **Production** (i Preview jeśli chcesz):

| Name | Value |
|---|---|
| `VITE_SUPABASE_URL` | `https://<ref>.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | anon key z Kroku 5b |
| `VITE_API_BASE_URL` | na razie `https://goat-api.onrender.com` (URL z Kroku 7c) — po DNS zmień na `https://api-goat.fmazurkiewicz.dev` |

5. **Deploy**.
6. Po sukcesie otwórz `https://<nazwa>.vercel.app` — strona powinna się załadować (login może jeszcze nie wracać na właściwy redirect, dopóki nie dodasz tego URL do Supabase Redirect URLs i Google origins).

W repo jest `frontend/vercel.json` (`rewrites` → `/index.html`) — potrzebne przy React Router, żeby **odświeżenie** podścieżki (`/settings`, `/chat`, …) nie dawało 404 Vercel.

### 8b. Tymczasowy redirect pod preview Vercel (opcjonalnie)

Jeśli testujesz zanim będzie `goat.fmazurkiewicz.dev`:

1. Supabase → Authentication → URL Configuration → dodaj Redirect: `https://<nazwa>.vercel.app/**`
2. Google Cloud → OAuth client → dodaj JavaScript origin: `https://<nazwa>.vercel.app`
3. Site URL możesz na chwilę ustawić na URL Vercel.

---

## Krok 9 — Cloudflare DNS

Domena `fmazurkiewicz.dev` jest już w Cloudflare (zgodnie ze standardem portfolio).

1. Wejdź na [https://dash.cloudflare.com](https://dash.cloudflare.com) → strefa **`fmazurkiewicz.dev`**.
2. **DNS** → **Records** → **Add record**.

**Rekord frontendu:**

| Pole | Wartość |
|---|---|
| Type | `CNAME` |
| Name | `goat` |
| Target | wartość z Vercel → Project → Settings → Domains (często `cname.vercel-dns.com`) |
| Proxy status | **DNS only** (szara chmura, nie pomarańczowa) |

3. **Add record** ponownie — **API:**

| Pole | Wartość |
|---|---|
| Type | `CNAME` |
| Name | `api-goat` |
| Target | hostname Render **bez** `https://`, np. `goat-api.onrender.com` |
| Proxy status | **DNS only** (obowiązkowo — pomarańczowy proxy psuje SSE) |

4. Save. Propagacja: zwykle kilka minut.

---

## Krok 10 — Custom domains w Vercel i Render

### 10a. Vercel

1. Project `goat` → **Settings** → **Domains**.
2. Add: `goat.fmazurkiewicz.dev` → Add.
3. Vercel pokaże status — gdy DNS się zgadza, pojawi się **Valid** / SSL Active.
4. (Opcjonalnie) ustaw ten domain jako Production.

### 10b. Render

1. Serwis `goat-api` → **Settings** → **Custom Domains**.
2. Add: `api-goat.fmazurkiewicz.dev`.
3. Poczekaj na weryfikację DNS + certyfikat.

### 10c. Env po DNS

1. **Vercel** → Environment Variables → edytuj:

```text
VITE_API_BASE_URL=https://api-goat.fmazurkiewicz.dev
```

2. Redeploy frontendu (Deployments → … → Redeploy), bo `VITE_*` są wbudowywane w build.
3. **Render** → Environment → upewnij się:

```text
CORS_ORIGINS=https://goat.fmazurkiewicz.dev
```

4. **Supabase** → URL Configuration:
   - Site URL: `https://goat.fmazurkiewicz.dev`
   - Redirect: `https://goat.fmazurkiewicz.dev/**`
5. **Google Cloud** → OAuth client → JavaScript origin: `https://goat.fmazurkiewicz.dev` (zostaw).

---

## Krok 11 — Smoke test produkcji

Wykonuj po kolei:

1. **Health API**

```powershell
curl https://api-goat.fmazurkiewicz.dev/api/health
```

→ 200. Jeśli timeout na Free Render: odczekaj ~1 min (cold start) i powtórz.

2. **Frontend** — otwórz `https://goat.fmazurkiewicz.dev`.
3. **Login Google** — przechodzi consent → wraca na domenę `goat` (nie błąd `redirect_uri_mismatch`).
4. W Supabase → **Authentication → Users** — widać Twoje konto.
5. Table Editor → **profiles** — wiersz z `id` = UUID usera (trigger z migracji).
6. W aplikacji: utwórz personę z szablonu.
7. Czat: wyślij wiadomość → pojawiają się tokeny (SSE).
8. (Opcjonalnie) generowanie planu → status joba kończy się sukcesem / partial.

---

## Checklist

| # | Co | OK? |
|---|---|---|
| 1 | Supabase project **`goat`** Active, `<ref>` i hasło DB zapisane | |
| 2 | Google OAuth client + redirect na `https://<ref>.supabase.co/auth/v1/callback` | |
| 3 | Supabase Provider Google ON + Site/Redirect pod `goat.fmazurkiewicz.dev` | |
| 4 | SQL: `0001_init` + `0002_exercise_catalog` bez błędów, seed OK | |
| 5 | Pooler URI (`+asyncpg`) + anon + service_role + JWKS | |
| 6 | OpenRouter key (+ soft limit) | |
| 7 | Render Docker `backend/`, env, `/api/health` = 200 | |
| 8 | Vercel `frontend/`, trzy `VITE_*`, deploy OK | |
| 9 | Cloudflare CNAME `goat` + `api-goat`, **DNS only** | |
| 10 | Custom domains TLS + `VITE_API_BASE_URL` + `CORS_ORIGINS` | |
| 11 | Smoke: login + persona + czat | |

---

## Typowe problemy

| Objaw | Co sprawdzić |
|---|---|
| `redirect_uri_mismatch` | Google redirect URI = dokładnie `https://<ref>.supabase.co/auth/v1/callback`; Site/Redirect w Supabase = domena frontu |
| CORS error w przeglądarce | `CORS_ORIGINS` na Render zawiera dokładny origin frontu (`https://goat.fmazurkiewicz.dev`) |
| API 502 / timeout pierwszy raz | Cold start Render Free — poczekaj i odśwież |
| Błąd DB / SSL na Render | `DATABASE_URL` przez **pooler :6543**, nie bezpośredni host `db.<ref>.supabase.co`; prefiks `postgresql+asyncpg://` |
| Czat „wisi”, SSE pada | Cloudflare Proxy na `api-goat` musi być **DNS only** |
| Login OK, ale brak profilu / FK | Migracja 0001 nie przeszła albo trigger na `auth.users` — sprawdź Table Editor |
| Frontend woła złe API | Po zmianie `VITE_*` trzeba **Redeploy** na Vercel |
| Odświeżenie `/settings` (itd.) → `404: NOT_FOUND` | Brak `frontend/vercel.json` SPA rewrite → `/index.html`; po dodaniu Redeploy |
