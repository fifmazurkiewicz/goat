# Plan: Widoczność konsultacji Goata + Pull-to-refresh (mobile)

**Data:** 2026-08-22
**Branch:** `feature/discussion`
**Speci:**
- `docs/superpowers/specs/2026-08-22-goat-consult-transparency-design.md` (istniejący, na gałęzi)
- `docs/superpowers/specs/2026-08-22-pull-to-refresh-design.md` (nowy)

## Decyzje

| # | Decyzja | Dlaczego |
|---|---|---|
| D1 | Konsultacje: rozwijany panel pod wiadomością Goata (domyślnie zwinięty), live przez nowy SSE event `consult_detail`, historia przez parowanie `tool_calls` ↔ `role='tool'` po `tool_call_id` | Dane już są w DB; nie zmieniamy modelu „kto mówi" (ADR-17) |
| D2 | Nie rozszerzamy kontraktu `tool_result` — osobny event `consult_detail` | Docstring `_tool_result_event_payload` jawnie zabrania surowego JSON; inni konsumenci nie dostaną nagle dużego tekstu |
| D3 | `question` dodane do JSON tool response `_consult_persona` (bez zmian schematu DB) | Historia dostaje komplet danych bez czytania argumentów z osobnej wiadomości assistant |
| D4 | PTR: soft refresh (`invalidateQueries()` globalnie), touch-only, wrapper w AppShell wokół `<Outlet />`, próg 72 px | User wybrał „wszędzie", mobile/dotyk, bez twardego reload; jeden punkt montażu = wszystkie ekrany |
| D5 | Prompt trenera w konsultacji zostaje bez zmian (opcja A ze speca) | To ten sam tekst, na bazie którego Goat i tak buduje odpowiedź; ewentualna opcja B po obserwacji jakości |
| D6 | `overscroll-behavior-y: none` na html/body | Wyłącza natywny PTR Chrome Android, który kolidowałby z własnym wskaźnikiem |

## Zadania

### A. Backend — widoczność konsultacji

1. **TDD:** test w `backend/tests/test_consult_persona.py`: happy path `_consult_persona` → JSON zawiera `question`; błąd → brak pola.
2. `orchestrator.py::_consult_persona`: dodać `"question": question` do zwrotki `status: ok`.
3. **TDD:** test: emit `consult_detail` tylko przy ok, payload `{tool_call_id, slug, persona_label, question, answer}`.
4. Przekazać `user_queue` + `tool_call_id` do `_consult_persona` (nowe parametry), emit po udanej odpowiedzi, obok istniejącego `tool_result`. Miejsce: przed kontynuacją syntezy Goata.

### B. FE — historia konsultacji

5. **TDD:** `chat-messages.test.ts`: `visibleChatMessages`/nowa funkcja buduje `consultDetails` na wiadomościach Goata z `role='tool'` (parowanie po `tool_call_id`, kolejność zachowana); malformed JSON pominięty; `role='tool'` nadal niewidoczny jako wiadomość.
6. `lib/chat-messages.ts`: rozszerzyć parsowanie o ekstrakcję konsultacji (typ `ConsultDetail {personaLabel, question, answer}`); wynik: `ChatMessage & { consultDetails?: ConsultDetail[] }`.
7. Typ `ChatMessage` FE: opcjonalne pole `consultDetails?`.

### C. FE — live konsultacje

8. **TDD:** typy SSE: nowy event `ChatStreamConsultDetailEvent` w unii.
9. `useChatTurnRunner.ts`: akumulacja `consultDetails` per turę analogicznie do `toolResults`; przy finalizacji tury (`finalizeStreamingTurn`) dopisanie do wiadomości Goata w cache React Query.

### D. UI — komponent

10. **TDD:** `ConsultDetails.test.tsx`: domyślnie zwinięty; rozwinięcie pokazuje pytanie + odpowiedź; brak renderu gdy puste; 2+ konsultacji = lista w kolejności.
11. `components/chat/ConsultDetails.tsx`: lista `<details>`-owych elementów pod bubble Goata (styl: mniejsza czcionka, ramka, wcięcie — „podgląd źródła", nie wiadomość trenera). Sprawdzić prymitywy w `components/ui`.

### E. Pull-to-refresh

12. `hooks/usePullToRefresh.ts`: pointer events (touch only), detekcja scrollerów (łańcuch przodków), tłumienie dystansu, próg 72 px, `isRefreshing`.
13. `components/layout/PullToRefresh.tsx`: wrapper z animowanym wskaźnikiem (transform translateY), spinner podczas refreshu.
14. `AppShell.tsx`: montaż wokół `<Outlet />`; `onRefresh` = `queryClient.invalidateQueries()`.
15. `index.css`: `overscroll-behavior-y: none` na html/body.
16. **TDD:** test hooka/wrappera: GWT-1..6 z speca (jsdom pointer events).

### F. Docs

17. `docs/technical/team-lead.md`: sekcja „Widoczność konsultacji" + diagram SSE (+`consult_detail`).
18. `docs/technical/ai-pipeline.md` §1a: wzmianka o `consult_detail`.
19. `docs/technical/architecture.md` §3a: `consult_detail` w liście eventów SSE.
20. `docs/technical/frontend.md`: `ConsultDetails` + sekcja PTR.
21. `AGENTS.md`: fakty (widoczność konsultacji; PTR mobile).

### G. Definition of Done

22. Backend: `pytest backend/tests -k "consult or chat"` zielony.
23. Frontend: `npm run lint && npm run test && npm run build` zielone.
24. Smoke w przeglądarce (desktop + devtools mobile emulation): konsultacja widoczna po rozwinięciu; PTR działa na emulowanym dotyku.

## Kolejność

A → B → C → D (pion konsultacji), potem E (PTR), F na końcu delta-docs. Testy czerwone przed każdą zmianą zachowania.
