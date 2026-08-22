# Goat (Kierownik Zespołu) — dokumentacja techniczna

**Status:** wdrożone (2026-08-04), **nowelizacja 2026-08-16** — Goat jako jedyny głos; konsultacja przez tool `consult_persona`  
**ADR:** [ADR-17](../adr/decisions.md#adr-17-kierownik-zespołu-goat--koordynacja-sesji-general)  
**Spec:** [2026-08-16-goat-consult-persona-design.md](../superpowers/specs/2026-08-16-goat-consult-persona-design.md)

## Przegląd

**Goat** to systemowa persona koordynująca sesję **Ogólna rozmowa** (`session_type=general`). User nie konfiguruje Goata — istnieje wyłącznie w kodzie (`TeamLeadSpeaker`, prompt w `team_lead.py`).

| Tryb | Kto mówi do usera |
|------|-------------------|
| Ogólna rozmowa **bez** `/slug` | **Goat · Kierownik Zespołu** — jedyny głos; eksperta dopytuje toollem `consult_persona` |
| `/slug` lub multi-slash | **Wybrana persona** — bezpośrednio (Goat nie startuje) |
| Prośba o plan tygodnia/miesiąca | **Goat** — `rebuild_plan` w swojej turze |

Sesja w UI nadal nazywa się **Ogólna rozmowa**.

Roster `consult_persona` = **aktywne persony tego usera** (te, które utworzył), nie sztywna lista ról produktu. Własne (`custom`) też wchodzą — slug z rosteru + zakres/zachowanie w prompcie Goata.

## Przepływ tury (`general`, bez slashy)

```mermaid
sequenceDiagram
    actor U as User
    participant GO as Goat
    participant T as consult_persona
    participant TR as Trener (backstage)

    U->>GO: wiadomość (general, bez slash)
    GO-->>U: tokeny (głos Goata)
    opt potrzebny ekspert
        GO->>T: slug + question
        T->>TR: handle_message client_visible=false
        TR-->>T: tekst
        T-->>GO: tool response
        Note over U: status „Goat konsultuje z {persona}…”
        GO-->>U: dalsze tokeny (synteza)
    end
```

Jedna tura SSE: `persona_turn_start` tylko dla Goata (`persona_id: null`). Zagnieżdżony trener nie emituje tokenów na kolejkę usera i nie zapisuje widocznej wiadomości `assistant` z `persona_id` trenera.

## Komponenty backend

| Plik | Odpowiedzialność |
|------|------------------|
| `backend/app/domain/chat/team_lead.py` | `TeamLeadSpeaker`, prompt tury, roster, `consult_scope_hint`, heurystyki planu/roundtable |
| `backend/app/domain/chat/orchestrator.py` | `run_chat_turn` — bez slashy tylko Goat; slash = pętla person; `_consult_persona` |
| `backend/app/domain/chat/tools.py` | `consult_persona` tylko w `get_team_lead_plan_tools()` |
| `backend/app/domain/chat/persona_scope.py` | Zakres roli `team_lead` + mapowanie typów |

### Heurystyki (wskazówki w prompcie Goata, nie wybór mówcy)

| Funkcja | Cel |
|---------|-----|
| `user_requests_plan_rebuild(message)` | Hint: wołaj `rebuild_plan` |
| `user_requests_all_trainers(message)` | Hint: skonsultuj wszystkich z rosteru |
| `consult_scope_hint(...)` | Hint slugów z **rosteru tego usera** (w tym `custom`) |

### Podział narzędzi

| Rola | Narzędzia |
|------|-----------|
| **Goat** | `get_plan`, `rebuild_plan`, `update_user_profile`, **`consult_persona`**, **`upsert_plan_items`** (dowolna aktywna persona; wymagane `persona_id` w entry), **`log_result`** (`source_persona_id=NULL`) |
| **Trenerzy** | `log_result`, `update_user_profile`, `get_plan`, `upsert_plan_items` (swoje) — **bez** `rebuild_plan` / `consult_persona` |

### Zapis wyników przez Goata (od 2026-08-17)

User raportuje trening w sesji `general` Goatowi, nie trenerowi — więc Goat zapisuje sam przez
`log_result`, bez pośrednictwa `consult_persona` (spec
[2026-08-17](../superpowers/specs/2026-08-17-mobile-history-and-goat-log-result-design.md)).
Wcześniej `log_result` było dla niego zablokowane, a po ograniczeniu consultów wyniki nie
zapisywały się wcale.

`results.source_persona_id = NULL` dla wpisów Goata — kierownik nie jest rekordem w `personas`
(jego `id` to sentinel `__team_lead__`), a kolumna ma FK na `personas(id)`. Funkcja
`_result_source_persona_id()` w orchestratorze mapuje personę na wartość kolumny; trenerzy
zapisują dalej z własnym UUID.

**Limit:** max 5 wywołań `consult_persona` na turę Goata.

**ADDED 2026-08-17 — latencja / brief planu**

- Goat **domyślnie bez** `consult_persona` (proste odpowiedzi i korekty planu samodzielnie).
- `rebuild_plan` przyjmuje opcjonalne `user_brief` (np. „bez badmintona”) — brief idzie do joba generacji; role wykluczone briefem (heurystyka `plan_brief_excludes_persona_type`) nie generują pozycji.
- Status startowy FE: „Goat przygotowuje odpowiedź…” (nie „uzgadnia z zespołem”).

**ADDED 2026-08-17 — ostateczny głos Goata nad planem**

- Persony szkicują; etap 3 harmonizacji = **Goat · Kierownik** (prompt + `user_brief` + deterministyczne usuwanie wykluczonych ról + patche `update`/`delete`).
- W UI postępu joba: wiersz Goata (Oczekuje / Harmonizuje… / Gotowe), nie anonimowa pigułka.
- W czacie Goat może `upsert_plan_items` na dowolną aktywną personę — ostateczna korekta bez pełnego rebuild.

### Slash (bez zmian)

`parse_multi_slash_command` → pętla person z `client_visible=True`. Goat nie startuje.

## Frontend

| Plik | Rola |
|------|------|
| `frontend/src/lib/team-lead.ts` | `TEAM_LEAD_DISPLAY_LABEL` |
| `frontend/src/lib/chat-status.ts` | chip „Konsultacja”, akcja „konsultuje” |
| `frontend/src/components/chat/ChatWindow.tsx` | Goat domyślnie; persona tylko gdy `persona_id` (slash) |
| `frontend/src/components/chat/ChatHeader.tsx` | Badge „Goat · Kierownik” |
| `frontend/src/hooks/useChatTurnRunner.ts` | `persona_turn_start` → `streaming.personaLabel` |

Wiadomości Goata w DB: `role=assistant`, `persona_id=NULL`.

## SSE (fragment)

```json
{"event": "persona_turn_start", "data": {"persona_id": null, "persona_label": "Goat · Kierownik Zespołu"}}
{"event": "persona_status", "data": {"persona_id": null, "persona_label": "Goat · Kierownik Zespołu", "phase": "tool", "message": "Goat konsultuje z Bartek · Trener motoryczny…", "tool_name": "consult_persona"}}
{"event": "tool_result", "data": {"tool_name": "consult_persona", "summary": "Skonsultowano: Bartek · Trener motoryczny", "success": true}}
{"event": "consult_detail", "data": {"tool_call_id": "call-1", "slug": "motoryka", "persona_label": "Bartek · Trener motoryczny", "question": "jak poprawić skok?", "answer": "Plyometria 2x tydzień."}}
```

## Widoczność konsultacji (ADDED 2026-08-22)

Spec: [2026-08-22-goat-consult-transparency-design.md](../superpowers/specs/2026-08-22-goat-consult-transparency-design.md).
User może **podejrzeć** pytanie Goata i odpowiedź trenera z `consult_persona` — rozwijany panel (`ConsultDetails`) pod wiadomością Goata, **domyślnie zwinięty**. Nie zmienia to modelu „kto mówi" (ADR-17): trener nie ma własnej bąbelkowej wiadomości.

| Warstwa | Mechanizm |
|---------|-----------|
| Backend tool response | `_consult_persona` zwraca JSON z `question` + `answer` (+ `persona_label`) → persystowane jak dotąd w `role='tool'` |
| Backend SSE | nowy event `consult_detail` (payload wyżej), emitowany tylko przy `status=ok`, obok `tool_result`; wymaga `tool_call_id` przekazanego do `_consult_persona` |
| FE live | `useChatTurnRunner` akumuluje `consult_detail` per turę; finalizacja dopina `consultDetails` do wiadomości Goata w cache (dedup po `tool_call_id`) |
| FE historia | `visibleChatMessages` paruje `assistant.tool_calls` (`consult_persona`) ↔ `role='tool'` po `tool_call_id` (trzymany w `chat_messages.tool_calls.tool_call_id`); błędy/malformed JSON pomijane |
| FE UI | `frontend/src/components/chat/ConsultDetails.tsx` — Accordion, tap target ≥ 44px, styl „podglądu źródła" |

Stare wpisy historii bez `question` w JSON renderują się z pustym pytaniem.

## Sesja `persona` (1:1)

Goat **nie** uczestniczy. Trener nie ma `rebuild_plan` — pełna harmonizacja wymaga sesji `general` lub zakładki Plany.

## Powiązane

- [ai-pipeline.md](./ai-pipeline.md) §1a, §3
- [persona_scope.py](../../backend/app/domain/chat/persona_scope.py)
- Migracja `0009_persona_role_boundaries.sql` — granice ról we wszystkich template safety
