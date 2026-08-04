# Design: Multi-persona tury czatu + toole Planów

**Data:** 2026-08-04  
**Status:** uzgodnione w brainstormingu; Faza 1 (statusy FE) wdrożona na `feature/chat-streaming-status`

## Cel produktowy

Persony w czacie mają działać jak zespół trenerów: gdy pytanie styka się z ≥2 rolami (albo user poda kilka slashy), system oddaje **osobne wiadomości sekwencyjnie**. Persony mają też **czytać / edytować / przebudowywać plan** w zakładce Plany, z **uzgodnieniem między wszystkimi aktywnymi personami** (nie izolowana edycja jednego trenera).

## Fazy

| Faza | Zakres | Zależności |
|------|--------|------------|
| **1** (done) | Linia statusu PL z `persona_turn_start` / `tool_call_start` | — |
| **2** | Routing → N person; sekwencyjne N odpowiedzi w jednej turze SSE | Faza 1 (statusy) |
| **3** | Toole czatu: odczyt planu, upsert pozycji, przebudowa (pipeline 1–3) | Faza 2 zalecana (narada przy przebudowie); działa też bez niej |

## Uzgodnienia UX / zachowania

1. **Multi-reply zawsze, gdy routing uzna za stosowne** (≥2 role) **lub** user wymieni kilka person slashami.
2. **Sekwencyjnie** (A): persona 1 kończy (tokeny + toole), potem 2, itd. — jeden aktywny status naraz.
3. **Plan:** odczyt + edycja pozycji dnia + przebudowa; przebudowa = istniejący 3-etapowy pipeline (wszystkie aktywne persony + harmonizacja).
4. **Hybryda edycji:** mała zmiana dnia → `upsert_plan_items` (+ opcjonalnie lekka harmonizacja etapu 3 na dotkniętych dniach w backlogu MVP-lite: najpierw sam upsert); „przebuduj / ułóż tydzień” → `rebuild_plan` = `POST /plans/generate` w tle.
5. Statusy FE mapują nowe toole (`get_plan` → „przegląda plan”, `upsert_plan_items` → „zapisuje w Plany”, `rebuild_plan` → „uzgadnia plan…”).

## Świadomie poza MVP Faz 2–3

- Równoległe / przeplatane tokeny wielu person.
- Pełna harmonizacja (etap 3) po każdym drobnym upsertcie (koszt) — najpierw upsert bez auto-harmonizacji; etap 3 tylko przy `rebuild_plan`.
- Zmiana ContextBuilder tak, by persona X widziała odpowiedzi innych person w tej samej turze (nadal filtr per `persona_id`; synchronizacja planu idzie przez DB `plan_items`, nie przez historię czatu).
- Narzędzie do usuwania całego planu / zmiany `period_type` z czatu.

## ADR

**Supersedes fragment ADR-13:** „dokładnie jedna persona na turę” → „jedna lub wiele person **sekwencyjnie** w jednej turze użytkownika, gdy routing / multi-slash tak zdecyduje”. Sesja `general`, atrybucja `chat_messages.persona_id`, event `persona_turn_start` — bez zmian modelu danych.

## Kontrakt (skrót)

### Faza 2 — routing

```ts
// RoutingResult (BE)
{ persona_ids: string[]; invoked_via: 'slash_command' | 'auto_routed' | 'multi_slash'; content: string }
```

- Klasyfikator JSON: `{ "persona_ids": ["uuid", ...] }` — 1..min(N_active, 3) unikalnych id z allowlisty.
- Multi-slash: wszystkie `/slug` na początku wiadomości (kolejność = kolejność odpowiedzi), reszta = wspólna treść.
- SSE: powtórzone `persona_turn_start` → tokeny/toole → … → jedno `done` na końcu całej tury.
- FE: po zakończeniu tury persony (przed następną) dopisać ukończoną odpowiedź do cache historii (optimistic), wyczyścić `content` streamu, zachować chipy tooli per tura lub scalić w listę.

### Faza 3 — toole

| Tool | Zachowanie |
|------|------------|
| `get_plan` | Opcjonalne `start_date`/`end_date`; zwraca skrót aktywnego planu + items w zakresie |
| `upsert_plan_items` | Batch insert/update pozycji dla `persona_id` wołającej (lub jawnego id jeśli w allowliście usera); walidacja `PlanItemContent` |
| `rebuild_plan` | Tworzy job jak `POST /plans/generate`; tool response = `{job_id, status}` + FE invaliduje `plans` + banner joba |

Błąd walidacji → tool response JSON do modelu, nigdy 500 (wzorzec `log_result`).
