# Uruchomienie lokalne

Projekt musi dać się w pełni uruchomić lokalnie — backend i frontend — bez Dockera i bez deployu na Render/Vercel.

## 1. Baza danych

Rekomendowane: **Supabase Cloud, projekt dev** (`coach-dev`) — najszybszy start, RLS działa tak samo jak na produkcji.

1. Utwórz projekt `coach-dev` w Supabase (Free tier).
2. Skonfiguruj Google OAuth: Dashboard → Authentication → Providers → Google (Client ID/Secret z Google Cloud Console).
3. Dodaj redirect URL `http://localhost:3000/**` w Authentication → URL Configuration.
4. Zastosuj migracje: `supabase link --project-ref <dev-ref>` → `supabase db push`.

Alternatywa: natywny lokalny Postgres 16 (`createdb coach_dev`) + `psql -f supabase/migrations/*.sql` ręcznie — wymaga własnej konfiguracji auth (poza zakresem tego dokumentu, Supabase Cloud jest prostsze).

## 2. Backend

```bash
cd backend
uv sync
cp ../.env.example .env
# uzupełnij DATABASE_URL, SUPABASE_URL, SUPABASE_JWKS_URL, OPENROUTER_API_KEY
uv run uvicorn app.main:app --reload --port 8000
```

Wartości sekretów (klucz OpenRouter, Supabase keys) uzupełnij samodzielnie — nigdy nie wklejaj ich do czatu/repo.

## 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# uzupełnij VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

## 4. Smoke test

1. `curl http://localhost:8000/api/health` → `200 OK`.
2. Otwórz `http://localhost:3000`, zaloguj się przez Google (dev Supabase project).
3. Utwórz personę (galeria 6 szablonów), wyślij testową wiadomość w czacie → zweryfikuj streaming SSE (tokeny na żywo) i inline chip przy zapisaniu wyniku.
4. Wygeneruj plan tygodniowy → zweryfikuj że `job_id` jest zwracany i frontend pollinguje aż do statusu `success`/`partial_success`.
5. Sprawdź `/results` — wykres trendu dla zalogowanej metryki.

## Uwagi

- Backend nie wymaga Dockera do developmentu — Docker jest używany wyłącznie w Dockerfile do deployu na Render i w CI do testów migracji.
- `backend/.env` i `frontend/.env.local` nigdy nie trafiają do repo (`.gitignore`).
