# DevOps i deploy

## 1. Render (backend)

| Ustawienie | Wartość |
|---|---|
| Typ | Web Service, Docker |
| Root Directory | `backend/` |
| Region | Frankfurt |
| Plan | Free na start |
| Health Check | `/api/health` |
| Build Filter | `backend/**` (zmiany w frontend/docs nie triggerują redeployu) |

`backend/Dockerfile` z `ca-certificates` (SSL do Supabase), `uvicorn` bindujący `0.0.0.0:$PORT`.

**Decyzja: BEZ osobnego Render Background Workera.** Generowanie planu w tym samym procesie web (`BackgroundTasks`), tabela `plan_generation_jobs`/`plan_generation_job_personas` daje widoczność/retry/partial-success bez potrzeby drugiego serwisu. Uzasadnienie i próg migracji: [`../adr/decisions.md`](../adr/decisions.md#adr-1-generowanie-planu-bez-osobnego-workera).

**Do zweryfikowania empirycznie po pierwszym wdrożeniu:** czy aktywny `BackgroundTasks` (bez otwartego requestu HTTP) liczy się jako "ruch" chroniący Render Free przed autosleep po 15 min bezczynności. Jeśli nie — długi job może zostać przerwany w połowie; reaper przy starcie aplikacji oznaczy go jako `error` (user klika "generuj ponownie" ręcznie na MVP, bez automatycznego requeue).

## 2. SSE na Render Free

Realny problem: proxy zrywa idle SSE connections. Rozwiązanie: heartbeat co 15s (`sse-starlette` ma to wbudowane przez `ping=15`), `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Do potwierdzenia empirycznie z symulowaną ciszą 20-30s przed produkcją.

## 3. Vercel (frontend)

| Ustawienie | Wartość |
|---|---|
| Framework | Vite |
| Root Directory | `frontend/` |
| Build/Output | `npm run build` / `dist` |
| Env prefix | `VITE_` |
| Plan | **Hobby** (potwierdzone — skala 2-5 userów, użytek niekomercyjny) |
| Ignored Build Step | pomija build gdy zmiany tylko w `backend/`/`docs/`/`supabase/` |

SPA (Vite), żadnych Vercel Serverless Functions — wywołania API bezpośrednio z przeglądarki do Render.

## 4. Uruchomienie lokalne — WYMAGANE (backend i frontend)

Pełna checklista w [`local-setup.md`](local-setup.md). Zasada: projekt musi dać się uruchomić lokalnie bez Dockera i bez deployu — produkcja nie jest jedynym sposobem pracy.

## 5. Sekrety i zmienne środowiskowe

| Zmienna | Gdzie żyje | Uwagi |
|---|---|---|
| `DATABASE_URL` | lokalny `.env` (localhost:5432 lub Supabase dev) / Render | Render: przez Supavisor pooler, nie bezpośrednio `db.<ref>.supabase.co` (IPv6-only) |
| `SUPABASE_URL` | lokalny / Render | |
| `SUPABASE_JWKS_URL` | lokalny / Render | `PyJWKClient(cache_keys=True, lifespan=300)` — cache, nie fetch przy każdym requeście |
| `SUPABASE_SERVICE_ROLE_KEY` | **tylko** Render (secret) | Backend-only, Admin API. Nigdy w repo/frontendzie |
| `OPENROUTER_API_KEY` | Render (secret) | |
| `OPENROUTER_CHAT_MODEL` / `OPENROUTER_PLANNER_MODEL` | Render + `.env.example` | env-driven, nie hardkodowane |
| `CORS_ORIGINS` | Render | `https://goat.fmazurkiewicz.dev` (+ `http://localhost:3000` gdy testujesz API lokalnie) + regex `*.vercel.app` dla preview |
| `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE_URL` | Vercel + `frontend/.env.local` | Publiczne, bezpieczne w bundlu (chronione przez RLS) |

Zasady: `SUPABASE_SERVICE_ROLE_KEY`, `OPENROUTER_API_KEY`, `DATABASE_URL`, `SUPABASE_ACCESS_TOKEN` (CLI) — nigdy do repo/frontendu. `.gitignore` obejmuje `.env`, `.env.*` poza `!.env.example`, `frontend/.env.local`.

## 6. Migracje Supabase

Projekt Supabase: **`goat`** (jeden cloud na start; osobny `goat-dev` tylko gdy świadomie rozdzielisz środowiska). `supabase/migrations/*.sql` jako jedyne źródło prawdy (**nie** Alembic).

1. Cloud (aktualny setup): migracje przez SQL Editor albo `supabase link` + `supabase db push` — patrz [`cloud-setup.md`](cloud-setup.md).
2. CI (`migrations-check` przy każdym PR): Postgres w kontenerze CI, aplikacja migracji od zera.
3. Kolejne migracje na prod: **ręczny, świadomy krok**, nie auto-apply na push do main.

## 7. Autentykacja — Google OAuth (bez magic linka)

**Decyzja:** wyłącznie Google OAuth przez Supabase Auth. Redirecty: `https://goat.fmazurkiewicz.dev/**` (prod); `http://localhost:3000/**` dodajesz gdy wrócisz do local. Szczegóły: [`cloud-setup.md`](cloud-setup.md).

## 8. CI/CD — `.github/workflows/ci.yml`

Trzy równoległe joby (path-filtered):
- `backend-lint-test` — `ruff check`, `ruff format --check`, `mypy` (min. `domain/`, `llm/`), `pytest`.
- `frontend-lint-build` — `eslint`, `vite build`.
- `migrations-check` — Postgres w kontenerze CI, aplikacja wszystkich migracji od zera.

Deploy do prod automatyczny przez natywne integracje Render/Vercel po merge; migracje prod pozostają ręcznym krokiem (sekcja 6).

## 9. Monitoring

Logi Render (wbudowane), Sentry free tier (backend Python SDK + frontend React SDK), health check monitorowany natywnie przez Render, limit wydatków ustawiony w panelu OpenRouter (soft limit + alert mailowy) — bez budowania własnej infrastruktury alertingu.

## 10. Cloudflare DNS

| Typ | Nazwa | Wartość | Proxy |
|---|---|---|---|
| CNAME | `goat` | `cname.vercel-dns.com` | DNS only |
| CNAME | `api-goat` | `<service>.onrender.com` | DNS only (podwójny proxy koliduje z SSE) |

## 11. Koszt

~$0-10/mies. na fazę dev/testów (tylko OpenRouter). Pierwszy próg płatności: **Supabase Pro $25/mies.** przy wyjściu z czystego testowania (Free pauzuje projekt po 7 dniach bezczynności). Render Starter $7/mies. dopiero gdy cold start realnie przeszkadza. Bez Render Workera (decyzja) — nie ma tego kosztu w ogóle.

## 12. Poza zakresem MVP

Import/synchronizacja Garmin/Strava/Apple Health — "może kiedyś", brak wpływu na architekturę teraz (generyczny model `results` to udźwignie).
