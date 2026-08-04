# Architektura — Multi-Persona Coaching App

## 1. Przegląd

Monorepo: `backend/` (FastAPI, Render), `frontend/` (Vite+React, Vercel), `supabase/migrations/` (jedyne źródło prawdy schematu).

```
coach-app/
├── backend/app/
│   ├── api/routers/      # personas, chat, results, plans, admin, health — CIENKIE
│   ├── core/             # config, security (JWT+JWKS), middleware, rate_limit, exceptions
│   ├── domain/
│   │   ├── chat/         # ChatOrchestrator, ContextBuilder, routing.py (ChatRoutingService — ADR-13)
│   │   ├── plans/        # PlanOrchestrator (3-etapowy), jobs runner
│   │   ├── personas/     # PersonaService, resolve_persona_columns()
│   │   ├── moderation/   # ModerationService (klasyfikator + runtime guard)
│   │   └── usage/        # UsageLimitService (atomic increment+check, budżet USD — ADR-16)
│   ├── llm/
│   │   ├── openrouter_client.py   # transport (httpx)
│   │   ├── streaming.py           # parser SSE OpenRoutera -> zdarzenia domenowe
│   │   └── tool_calling.py        # akumulacja fragmentów tool_call
│   ├── repositories/     # cała wiedza SQL, jedyne miejsce dotykające DB
│   └── models/ / schemas/
├── frontend/src/
│   ├── pages/  ├── components/  ├── lib/  └── store/
├── supabase/migrations/
└── .github/workflows/
```

Zasada: routery są cienkie (parsing + wywołanie orkiestratora), cała logika biznesowa żyje w `domain/`, cała wiedza SQL w `repositories/`. Domenowe serwisy to zwykłe klasy Pythona (Protocol dla zależności) — nie znają FastAPI, żeby dało się je testować bez bazy/HTTP.

## 2. Baza danych — dostęp i RLS

**SQLAlchemy 2.0 Core** (nie pełny ORM) + `asyncpg` — migracje idą osobnym torem (Supabase CLI, surowy SQL), więc ORM-owe mapowanie relacji/migracji byłoby dublowaniem systemu.

**RLS przez Supavisor (transaction mode) — konkretny wzorzec:**

- `NullPool` w `create_async_engine` — pooling robi Supavisor, nie dublujemy go w aplikacji.
- `connect_args={"statement_cache_size": 0}` — **obowiązkowe**. `asyncpg` domyślnie cache'uje prepared statements po stronie klienta; w trybie transaction Supavisor przydziela inne fizyczne połączenie do każdej transakcji, więc statement przygotowany na jednym backendzie nie istnieje na kolejnym (`prepared statement does not exist`).
- `SET LOCAL` (nigdy `SET`) + `set_config('request.jwt.claims', json, true)` — ustawiane w tej samej transakcji co zapytania, cofa się automatycznie na `COMMIT`/`ROLLBACK`. `SET` sesyjne przeciekłoby między userami przy współdzielonym fizycznym połączeniu.
- `service_role` — osobny silnik/DSN, używany **wyłącznie** do Supabase Admin API i `/admin/*`, nigdy jako fallback domyślnej zależności. Endpointy `/admin/*` mają jawną, kodową weryfikację `profiles.is_admin` — ukrycie w UI to nie jest autoryzacja.
- Format claimów musi być spójny z tym, czego oczekują polityki RLS w migracjach SQL (typowo `auth.uid()` czyta `request.jwt.claims->>'sub'`) — to współdzielony kontrakt między SQL a kodem backendu, udokumentowany w [`database-schema.md`](database-schema.md).

## 3. Chat — SSE + multi-turn tool calling

Backend jest **aktywnym agregatorem**, nie 1:1 tunelem SSE z OpenRoutera do frontendu.

**Implementacja:** `sse-starlette` (`EventSourceResponse`, wbudowany `ping=15` heartbeat — Render proxy zrywa idle SSE connections, heartbeat temu zapobiega). Wzorzec producer/consumer przez `asyncio.Queue`:

```python
async def chat_stream_endpoint(request: Request, ...):
    queue: asyncio.Queue[dict] = asyncio.Queue()
    orchestrator_task = asyncio.create_task(run_chat_orchestrator(ctx, queue))

    async def event_generator():
        try:
            deadline = asyncio.get_event_loop().time() + settings.chat_hard_timeout_s
            while True:
                if await request.is_disconnected():
                    orchestrator_task.cancel()
                    break
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    orchestrator_task.cancel()
                    yield {"event": "error", "data": '{"code":"timeout"}'}
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=min(15, remaining))
                except asyncio.TimeoutError:
                    continue  # sse-starlette samo wyśle ping
                yield event
                if event["event"] in ("done", "error"):
                    break
        finally:
            if not orchestrator_task.done():
                orchestrator_task.cancel()

    return EventSourceResponse(event_generator(), ping=15)
```

**Pętla orkiestratora (`run_chat_orchestrator`):**

1. `httpx.AsyncClient.stream("POST", ..., tools=[log_result_schema])` do OpenRoutera.
2. `delta.content` → `queue.put({"event": "token", ...})`.
3. `delta.tool_calls` (fragmenty: `id`+`name` w pierwszym chunku, `arguments` doklejane kawałkami) → akumulacja w buforze `dict[int, ToolCallBuffer]` keyed po `index`, aż `finish_reason == "tool_calls"`.
4. Parsowanie JSON argumentów + walidacja Pydantic (**niezaufany input mimo że pochodzi z "naszego" modelu**) → wykonanie `log_result` (batch, patrz [`ai-pipeline.md`](ai-pipeline.md)) → zapis do `results`.
5. Zapis `assistant` message (z `tool_calls`) + `tool` message (z wynikiem) **w jednej transakcji** — inaczej crash między nimi zostawia niespójną historię.
6. Kolejny request do OpenRoutera z pełną historią → powtórz aż `finish_reason == "stop"` lub **twardy limit 3-5 rund** (chroni przed pętlą/kosztem).
7. `queue.put({"event": "tool_result", "data": {"tool_name", "summary", "success"}})` po każdym
   zapisie — frontend pokazuje inline chip (nie surowy JSON tool response).

**Krytyczne — połączenie DB nie może żyć przez cały czas streamu.** Endpoint czatu NIE bierze długożyjącej zależności DB przez `Depends`. Orkiestrator otwiera krótkie transakcje tylko na moment zapisu (per rundę), zwalniając połączenie natychmiast — inaczej przy kilku równoległych czatach (60-90s każdy) szybko wyczerpuje się pula Supavisor.

**Cancellation:** `request.is_disconnected()` → `orchestrator_task.cancel()` → poprawnie przerywa `httpx.AsyncClient.stream` (zamyka połączenie w `finally`). Orkiestrator nie może łapać `asyncio.CancelledError` szerokim `except Exception`.

**Frontend SSE eventy (kontrakt):** `token`, `tool_call_start`, `tool_result`, `done`, `error`, oraz `persona_turn_start` (patrz niżej) — zdefiniowane jako współdzielony JSON Schema/Pydantic model, żeby frontend i backend nie rozjechały się na nazwach pól.

### 3a. "Ogólna rozmowa" — auto-routing i wywołanie persony komendą `/slug` (ADR-13)

Obok sesji `persona` (1:1, opisanej wyżej — bez zmian w jej logice) istnieje sesja `general`
(`chat_sessions.session_type='general'`, `persona_id IS NULL`). W sesji `general` backend
**najpierw koordynuje turę przez Kierownika Zespołu (Goat, ADR-17)**, potem deleguje do 1..N
trenerów sekwencyjnie (max 3):

1. **`TeamLeadService.plan_consultation`** — wybór person + brief per trener:
   - **Parsowanie `/slug` / multi-slash** — deterministyczne, zero LLM (`parse_multi_slash_command`).
   - **Dokładnie jedna aktywna persona** — bez LLM kierownika.
   - **≥2 aktywne persony, brak slashy** — jedno wywołanie `chat_model` z `json_schema`
     (`persona_ids[]`, `team_brief`, `per_persona_briefs`, `status_message`).
   - Emitowane: `team_phase` (`planning` → `delegating`), `team_status`.
2. **Opcjonalna tura Goata (widoczna w UI)** — gdy `user_requests_plan_rebuild(content)`:
   - `TeamLeadSpeaker` woła `rebuild_plan`; etykieta SSE/DB: **„Goat · Kierownik Zespołu”**,
     `persona_id IS NULL`.
   - Gdy `is_plan_coordination_only` — po Goacie samo `done` (trenerzy pominięci).
3. **Pętla trenerów** — każda persona przez `ChatOrchestrator.handle_message` z
   `build_consultation_user_message` (brief + rekomendacje poprzednich w tej turze).
   Narzędzia: `get_trainer_chat_tools()` — **bez** `rebuild_plan`.
4. Backend emituje `persona_turn_start {persona_id, persona_label}` przed tokenami **każdej**
   tury (Goat: `persona_id=null`); `done` **raz** na końcu tury usera.
5. `ContextBuilder` filtruje historię per `persona_id` trenera (Goat: pełna historia sesji
   `general` bez filtra persona).

Szczegóły: `docs/technical/team-lead.md`. Legacy `ChatRoutingService` (`routing.py`) nie jest
wołany z orchestratora — do deprecacji (P2).

**Aktualizacja (2026-08-04):** routing może zwrócić wiele `persona_ids` (klasyfikator Goat lub
multi-slash `/a /b treść`). Świadomie odrzucone: równoległe / przeplatane tokeny.

Narzędzia czatu: trenerzy — `get_plan`, `upsert_plan_items`, `log_result`, profil; Goat —
`get_plan`, `rebuild_plan` (pipeline 3-etapowy).

## 4. Generowanie planu — pipeline (decyzja: priorytet to SYNCHRONIZACJA między personami)

Generowanie planu ma **przede wszystkim** dawać spójny, zsynchronizowany plan między wszystkimi aktywnymi personami (dieta pod trening, regeneracja uwzględniona, brak konfliktów obciążenia) — to ważniejsze niż maksymalna jakość pojedynczej persony w izolacji. Stąd **trzy etapy**, nie dwa:

```
Etap 1 — COORDINATOR PASS (tani model)
  Input: aktywne persony (role), ostatnie wyniki, poprzedni plan
  Output: wspólny szkielet — rozkład dni treningowych/odpoczynku, priorytety,
          orientacyjne cele (np. cel kaloryczny, dni intensywne vs regeneracyjne)
  ~500-1000 tok. output, niski koszt

Etap 2 — PER-PERSONA GENERACJA (PLANNER_MODEL, RÓWNOLEGLE — asyncio.gather)
  Każda persona dostaje: swój system_prompt + swoje kolumny/detail_level +
  swoje wyniki + szkielet z etapu 1 jako wspólny kontekst
  Output: PlanItemContent (draft) dla swoich dni
  Walidacja + retry PER PERSONA osobno (nie całościowo)

Etap 3 — HARMONIZACJA / "zarządca kalendarza" (PLANNER_MODEL)
  Input: WSZYSTKIE draft plan_items z etapu 2 razem + system prompty person
  Zadanie: wykryć i skorygować konflikty (np. ciężki trening nóg + długi bieg
  tego samego dnia, dieta niedopasowana do dnia treningowego, brak odpoczynku),
  dopisać cross-referencing notes między personami, finalizować kalendarz.
  Output: TARGETED PATCHE do konkretnych plan_items (nie pełna regeneracja
  wszystkiego — kontrola kosztu), albo potwierdzenie że draft jest spójny.
```

**Uzasadnienie 3 etapów zamiast pojedynczego mega-promptu:** przy 5 personach output dla planu miesięcznego sięga 20-45k tokenów w jednym wywołaniu — realne ryzyko ucięcia JSON w połowie i "rozmycia" jakości dla dalszych person w kolejce. Rozbicie na małe, równoległe wywołania + osobna warstwa harmonizacji daje kontrolowany koszt, tani retry (per persona, nie całość) i **explicit krok odpowiedzialny za spójność międzypersonową**, czego wymaga priorytet "przede wszystkim zsynchronizowane".

Pojedyncze wywołanie (bez etapu 1 i 3) dopuszczalne tylko przy 1-2 aktywnych personach + plan tygodniowy — tam ryzyko jest niskie i jest to tańsze.

### Background job — bez osobnego workera na Render

**Decyzja (potwierdzona):** generowanie planu wykonywane jest w tym samym procesie co web (`BackgroundTasks` FastAPI), **bez** osobnego Render Background Workera. Uzasadnienie i próg migracji w [`devops.md`](devops.md) i [`../adr/decisions.md`](../adr/decisions.md#adr-1).

Model stanu (obsługa partial success — 4/5 person ok, 1 zawiodła nawet po retry):

- `plan_generation_jobs(id, plan_id, status, error_message, attempts, created_at, started_at, finished_at)` — status: `pending|running|success|partial_success|error`, **pochodna** stanu per-persona.
- `plan_generation_job_personas(job_id, persona_id, status, retry_count, last_error)` — per-persona granularność.
- Retry pojedynczej persony **reużywa ten sam `job_id`** (nie tworzy nowego) — inaczej niezmiennik "max 1 aktywny job na usera" (partial unique index w bazie, patrz [`database-schema.md`](database-schema.md)) pęka przy pierwszym partial failure.
- **Reaper** przy starcie aplikacji (`startup` event): joby `running` starsze niż 5 min → oznacz jako `error` (chroni przed zawieszeniem po restarcie Render). Na MVP reaper **nie wznawia** automatycznie — user klika "generuj ponownie" ręcznie.
- Frontend polluje `GET /plans/jobs/{id}` z breakdown per-persona; UI obsługuje `partial_success` jako osobny stan (nie binarnie success/error) — pokazuje częściowy plan + baner z listą person, dla których się nie udało, z akcją retry.

### Konkurencja — pułapki asyncio

- `asyncio.gather(*persona_tasks, return_exceptions=True)` dla per-persona retry — **nie** `asyncio.TaskGroup` (anuluje wszystko przy pierwszym wyjątku, odwrotność pożądanego zachowania).
- Każda coroutine bierze **własne** połączenie DB z puli (`engine.connect()`), nigdy współdzielone między coroutines.
- `asyncio.Semaphore` ograniczający równoczesne LLM/DB calls, dobrany do limitu Supavisora i planu Render Free.
- Blokujące operacje (np. tiktoken na dużym tekście) przez `asyncio.to_thread` — Render Free to prawdopodobnie 1 worker uvicorn, blokada zamraża wszystkie aktywne streamy SSE innych userów.

## 5. Kontekst czatu — zarządzanie tokenami

- **Profil użytkownika (`user_profile`)**: deterministyczny, zwięzły blok (waga/wzrost/wiek/poziom aktywności/cel) doklejany do system promptu przy KAŻDEJ wiadomości — to dane rzadko się zmieniające, tanie do wstrzyknięcia zawsze. Gdy niekompletny, `ContextBuilder` dokleja dodatkowo dynamiczną instrukcję "dopytaj o brakujące dane" — patrz [`ai-pipeline.md`](ai-pipeline.md#0-profil-użytkownika--personalizacja-waga-wzrost-wiek-cel) sekcja 0.
- **Wyniki (`results`)**: deterministyczne query ostatnich N rekordów per kategoria, **bez** LLM-owej sumaryzacji (niepotrzebny koszt/niedeterminizm).
- **Historia czatu**: sliding window ostatnich M wiadomości. **Decyzja: bez rolling summary w MVP** — dodać dopiero gdy dane z produkcji pokażą realne ucinanie istotnego kontekstu (data-driven, nie projektowane z góry). Stare wiadomości nigdy nie są kasowane z bazy.
- **Plan generation bazuje na `results` + poprzednim planie + `user_profile` + `persona_constraints`**, nie na historii/summary czatu (zbyt niedeterministyczne dla 3-etapowego pipeline'u). Twarde ograniczenia zdrowotne (np. kontuzja wspomniana w czacie) i dane biometryczne wymagają osobnego, jawnego mechanizmu — patrz [`ai-pipeline.md`](ai-pipeline.md).

## 6. Wyjątki i logging

Hierarchia `AppError` (`PersonaLimitExceededError`→409, `UsageLimitExceededError`→429, `ModerationRejectedError`→400, `ConflictError`→409, `ExternalServiceError`→502) + globalny exception handler FastAPI — routery bez `try/except`.

`structlog`, JSON w produkcji, `request_id`/`job_id` przez `contextvars` (dla background joba trzeba jawnie zbindować nowy kontekst — request context się nie propaguje automatycznie). Nigdy pełna treść promptów/wiadomości na poziomie INFO (PII + koszt).

## 7. DI i testowalność

Domenowe serwisy = klasy Pythona przyjmujące zależności w konstruktorze (Protocol dla `LLMClient`/repo), nie znają FastAPI. `Depends` żyje wyłącznie w `core/dependencies.py`. Testy jednostkowe instancjonują serwisy bezpośrednio z fake'ami — zero FastAPI, zero bazy.

Szczegóły strategii testów w [`ai-pipeline.md`](ai-pipeline.md) (golden cases) i [`devops.md`](devops.md) (CI).

## 8. Autentykacja

**Decyzja: wyłącznie Google OAuth przez Supabase Auth — bez magic linka.** Upraszcza UI logowania (jeden przycisk "Zaloguj się przez Google") i eliminuje potrzebę obsługi emaili transakcyjnych. Konfiguracja redirect URL w Supabase Auth settings, szczegóły w [`local-setup.md`](local-setup.md).

## 9. Limity — budżet kosztowy w USD per konto (ADR-16)

Zamiast planów Free/Pro (nieobecnych w reszcie specyfikacji — MVP jest non-commercial, kilku znanych
userów), `UsageLimitService` egzekwuje **jawny budżet w dolarach per konto**
(`profiles.usage_budget_usd`, domyślnie $10, edytowalny przez admina — dokładnie ten sam wzorzec co
`profiles.max_active_personas`, ADR-12).

- **Koszt liczony z odpowiedzi OpenRoutera** (`prompt_tokens`/`completion_tokens` zwracane w chunku
  `usage` na końcu streamu SSE — wymaga `usage: {include: true}` w request body OpenRoutera) ×
  cennik modelu. Cennik pobierany z `/api/v1/models` OpenRoutera i cache'owany in-memory (odświeżany
  okresowo, nie hardkodowany w kodzie — ceny modeli się zmieniają).
- `usage_limits.cost_usd_used` — suma kosztu w bieżącym okresie (`(user_id, period_start)`, ten sam
  wiersz co istniejące liczniki `messages_used`/`tokens_used`/`plan_generations_used`).
- **Atomowy check+increment** (ten sam wzorzec co liczniki): `UPDATE usage_limits SET cost_usd_used =
  cost_usd_used + :delta WHERE cost_usd_used + :delta <= (SELECT usage_budget_usd FROM profiles WHERE
  id = :user_id) RETURNING ...` — race-condition-safe przy równoległych requestach, bez osobnego
  SELECT-then-UPDATE.
- Koszt generowania planu (3 wywołania LLM per etap, patrz sekcja 4) debituje z TEGO SAMEGO budżetu co
  czat — jedna pula per user, nie osobne limity per funkcja.
- Przekroczenie budżetu → `UsageLimitExceededError` (429) z czytelnym komunikatem (kwota
  wykorzystana/limit, data odnowienia okresu) — `frontend.md` sekcja 10.
- Panel admina (`GET /admin/users`) pokazuje `cost_usd_used`/`usage_budget_usd` wprost jako kwotę,
  **bez** etykiet "Free"/"Pro" (odrzucone jako mylące — sugerują subskrypcję, której MVP nie ma).
