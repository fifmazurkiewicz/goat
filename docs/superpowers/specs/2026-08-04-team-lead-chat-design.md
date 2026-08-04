# Design: Kierownik zespołu, tytuły rozmów, tło czatu

**Data:** 2026-08-04  
**Status:** wdrożone (faza 1 + faza 2) + **odchylenie ADR-17** (Goat widoczny przy planie)

> **Kanon:** [docs/technical/team-lead.md](../../technical/team-lead.md) · **Audyt:** [docs/technical/audits/2026-08-04-goat-team-lead-audit.md](../../technical/audits/2026-08-04-goat-team-lead-audit.md)

## Analiza zespołu ekspertów (synteza)

### UX/UI
- Tytuł „Nowa rozmowa” na każdej sesji — brak auto-tytułu z pierwszej wiadomości; brak edycji (PPM) i usuwania.
- Statusy trenerów są, ale brak fazy „kierownik uzgadnia z zespołem” przed odpowiedziami.
- Nawigacja do Wyniki/Plan przerywa SSE (`abort` + `cancel` po stronie BE) — user traci turę.

### Architektura
- Routing (`ChatRoutingService`) wybiera persony, ale **nie koordynuje** — każda persona ma izolowaną historię (`persona_id` filter) i nie widzi rekomendacji innych w tej samej turze → model mówi „nie wiem co robi dietetyk”.
- Brak nadrzędnej roli „kierownik zespołu” (systemowa, niewidoczna dla usera).
- Brak kolejki zadań czatu — wszystko wiąże się z połączeniem SSE.

### AI / Python
- `ContextBuilder` ma profil usera, ale **nie** skrótu planów ani ostatnich wyników.
- `upsert_plan_items` wymaga istniejącego planu `ready|partial_ready` i blokuje edycję cudzych pozycji — kierownik nie może zapisać uzgodnionego planu za trenerów.

### Frontend
- `useChatStream` żyje w `ChatWindow` — unmount = abort. Wzorzec do skopiowania: `usePlanGenerationStore` + polling w `AppShell`.

## Decyzje produktowe

| Temat | Decyzja |
|-------|---------|
| Kierownik zespołu | Systemowa persona (prompt w kodzie); **widoczny jako „Goat · Kierownik Zespołu”** przy operacjach na planie; przy zwykłych pytaniach niewidoczny |
| Flow ogólnej rozmowy | (1) kierownik planuje konsultację → (2) status „Uzgodniam z…” → (3) trenerzy odpowiadają sekwencyjnie z briefem + rekomendacjami poprzednich → (4) `done` |
| Tytuł rozmowy | Auto z pierwszych ~60 znaków pierwszej wiadomości usera; edycja PATCH; PPM → „Zmień tytuł” / „Usuń” |
| Tło | BE nie anuluje orchestratora przy disconnect SSE; FE: globalny runner w AppShell (jak plan jobs) |
| Pamięć person | Bloki `[PLAN]` i `[OSTATNIE WYNIKI]` w system prompt + toole bez zmian |
| Zapis planu | `upsert_plan_items` akceptuje `persona_id` w entry (dowolna aktywna persona usera); kierownik może delegować zapis |

## Kontrakt SSE (rozszerzenie)

```ts
{ type: "team_status", message: "Uzgodniam z dietetykiem i trenerem…" }
{ type: "turn_complete" }  // opcjonalnie przed done — sygnał końca pracy zespołu
```

Istniejące: `persona_turn_start`, `token`, `tool_call_start`, `tool_result`, `done`, `error`.

## API (nowe)

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| PATCH | `/chat/sessions/{id}` | `{ title: string }` |
| DELETE | `/chat/sessions/{id}` | Usuwa sesję + wiadomości (kaskada FK) |
| GET | `/chat/sessions/{id}/turn-status` | `{ in_progress: bool }` |

## Poza zakresem tej iteracji

- Pełna tabela `chat_turn_jobs` w Postgres (Render Free = jedna instancja; rejestr in-memory wystarczy na start).
- Równoległe odpowiedzi trenerów (zostaje sekwencja).
- Widoczne wiadomości kierownika w czacie przy **operacjach na planie** (Goat); przy zwykłych pytaniach user widzi tylko trenerów.

## ADR (propozycja)

**ADR-17:** Sesja `general` jest koordynowana przez systemowego Kierownika Zespołu przed delegacją do person użytkownika. Routing slash/multi-slash pozostaje deterministyczny (pomija kierownika).

### Znane trade-offy (ADR-17, 2026-08-04)

| Scenariusz | Zachowanie |
|------------|------------|
| Plan-only bez pytań merytorycznych | Tylko Goat (`is_plan_coordination_only`) — trenerzy pominięci, nawet przy multi-slash |
| Plan-only | `build_plan_only_consultation` pomija LLM konsultacji (1 wywołanie mniej) |
| Multi-slash + plan-only | Slash wybiera persony w routingu, ale tura kończy się po Goacie |
| Retry streamu | Nie idempotentny dla `rebuild_plan` — może powtórzyć job planu |
| Sesja persona 1:1 | Brak Goata i `rebuild_plan` — harmonizacja przez Ogólną rozmowę lub zakładkę Plany |

Legacy `ChatRoutingService` zastąpiony przez `TeamLeadService` — do usunięcia w P2.

---

## Faza 2 — wdrożone rozszerzenia

| Temat | Implementacja |
|-------|----------------|
| SSE statusów | `persona_status` (thinking/writing/tool/wrapping_up/done), `team_phase`, `persona_turn_end` |
| Kolejka Postgres | `background_jobs` (`0008_background_jobs.sql`) + `domain/jobs/runner.py` |
| Auto-tytuł LLM | job `chat_title`, env `CHAT_LLM_TITLE_ENABLED=true` |
| Harmonizacja po upsert | job `plan_harmonize` na dotknięte dni, `PLAN_AUTO_HARMONIZE_ON_UPSERT=true` |
| Enqueue planów | `enqueue_plan_generation_async` — `/plans/generate` i `rebuild_plan` |
| Tura w tle | `chat_sessions.turn_in_progress` + rejestr in-memory |

### Kontrakt SSE (pełny)

```ts
{ type: "team_phase", phase: "planning" | "delegating", message: string }
{ type: "team_status", message: string }
{ type: "persona_turn_start", persona_id, persona_label }
{ type: "persona_status", persona_id, persona_label, phase, message, tool_name? }
{ type: "persona_turn_end", persona_id, persona_label }
{ type: "turn_complete" }
{ type: "token", text }
{ type: "tool_call_start", name }
{ type: "tool_result", tool_name, summary, success }
{ type: "done" } | { type: "error", message }
```

### Migracja

Uruchom `supabase/migrations/0008_background_jobs.sql` w SQL Editor (cloud + lokalny Postgres).
