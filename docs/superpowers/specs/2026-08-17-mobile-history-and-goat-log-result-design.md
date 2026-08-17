# Design: historia rozmów na mobile + zapis wyników przez Goata

**Data:** 2026-08-17
**Status:** zaakceptowane (user wybrał wariant C dla mobile, A dla wyników)
**Powiązane:** [ADR-6](../../adr/decisions.md#adr-6-log_result-jako-narzędzie-batch-nie-pojedynczy-wpis), [ADR-17](../../adr/decisions.md#adr-17-kierownik-zespołu-goat--koordynacja-sesji-general), [team-lead.md](../../technical/team-lead.md), [frontend.md](../../technical/frontend.md) §4, [2026-08-17-goat-plan-authority-design.md](./2026-08-17-goat-plan-authority-design.md)

> **Delta:** (1) `/chat` bez `:sessionId` na mobile przestaje być martwym empty state — pokazuje listę rozmów; przy wejściu do appki user ląduje w ostatniej rozmowie. (2) Goat dostaje `log_result` z `source_persona_id=NULL`.

## Problem

### P1 — historia niedostępna na telefonie

`ChatLayout` na mobile trzyma `PersonaSessionDrawer` wyłącznie w `Sheet` (zamknięty domyślnie), a jego jedyny trigger — hamburger „Lista rozmów” — żyje w `ChatHeader`, który renderuje się tylko przy `activeSession`. Wejście na `/chat` bez ID daje więc empty state bez żadnego dostępu do historii; user musi utworzyć nową rozmowę, żeby zobaczyć stare. Desktop tego nie odczuwa (drawer przyklejony na stałe).

### P2 — Goat nie zapisuje wyników

`TEAM_LEAD_CHAT_TOOL_NAMES` nie zawiera `log_result`, a `TEAM_LEAD_TURN_BEHAVIOR` mówi wprost „Nie wołaj log_result”. Pierwotne założenie ([spec consult_persona](./2026-08-16-goat-consult-persona-design.md) §Poza zakresem): wynik zapisze trener wywołany przez `consult_persona`. Po nowelizacji z 2026-08-17 („Goat domyślnie bez consult_persona”) ta ścieżka praktycznie nie odpala się — user raportuje trening Goatowi, Goat streszcza i prosi o potwierdzenie zapisu, ale nie ma czym zapisać.

## Wymagania (Given / When / Then)

### GWT-1 — auto-wejście w ostatnią rozmowę (mobile)

**Given** telefon, user ma ≥1 rozmowę
**When** wchodzi na `/chat` bez `:sessionId` po raz pierwszy od otwarcia appki
**Then** zostaje przekierowany (`replace`) do najnowszej rozmowy wg `updated_at`
**And** hamburger listy rozmów jest dostępny w headerze

### GWT-2 — lista rozmów jako ekran

**Given** telefon
**When** user jest na `/chat` bez `:sessionId` i auto-wejście już się wykonało (albo nie ma do czego wejść)
**Then** widzi pełnoekranową listę rozmów (`PersonaSessionDrawer`) z „Nowa rozmowa”
**And** nie następuje kolejny redirect (można zostać na liście)

### GWT-3 — brak rozmów

**Given** konto bez rozmów
**When** user wchodzi na `/chat`
**Then** widzi komunikat „Brak rozmów” + CTA „Nowa rozmowa”, bez redirectu

### GWT-4 — desktop bez zmian

**Given** desktop
**When** user wchodzi na `/chat`
**Then** stały drawer po lewej + empty state „Wybierz rozmowę z listy albo zacznij nową”
**And** brak auto-redirectu (lista jest już widoczna)

### GWT-5 — Goat zapisuje wynik

**Given** sesja `general`, user raportuje faktyczny wynik („dziś bench 4×8 @45 kg”)
**When** Goat woła `log_result` z entries
**Then** wpisy trafiają do `results` z `source='agent'`, `source_persona_id=NULL`
**And** FE pokazuje chip „Wynik”, `/results` widzi dane po invalidacji

### GWT-6 — brak regresji trenera

**Given** trener (`/slug`, sesja `persona`, consult backstage)
**When** woła `log_result`
**Then** zapis z `source_persona_id` = UUID trenera (jak dziś)
**And** trener nadal nie ma `rebuild_plan` / `consult_persona`

### GWT-7 — Goat nie fabrykuje wyników

**Given** rozmowa bez raportu wyniku (plan, pytanie, motywacja)
**When** Goat odpowiada
**Then** nie woła `log_result` (zasada „tylko jawnie zaraportowane wartości” z ADR-6 / preambuły)

## Podejście

### Frontend (`ChatLayout`)

```
/chat (mobile, brak :sessionId)
├─ sessions.length > 0 && !autoOpenedRef → navigate(latest.id, {replace: true})
└─ w przeciwnym razie → <PersonaSessionDrawer> na całą szerokość (ekran listy)

/chat (desktop) → jak dziś: drawer 288px + empty state
```

- Najnowsza rozmowa = max `updated_at` (te same dane co lista, bez nowego endpointu).
- Guard jednorazowości: `useRef` w `ChatLayout` (żywotność mountu shellu), nie localStorage — po powrocie na listę w tej samej sesji nie ma ponownego skoku.
- Auto-wejście dotyczy tylko mobile; desktop ma listę na ekranie, redirect byłby niepożądany.
- `sortSessionsByRecency` / `latestSessionId` jako czysta funkcja w `lib/chat-session.ts` → testowalna bez renderu.

### Backend (`log_result` u Goata)

| Element | Zmiana |
|---------|--------|
| `TEAM_LEAD_CHAT_TOOL_NAMES` | + `log_result` |
| `get_team_lead_plan_tools()` | bez zmian w kodzie (filtruje po nazwach) |
| `TEAM_LEAD_TURN_BEHAVIOR` | „Nie wołaj log_result” → „Wynik zaraportowany przez usera zapisuj sam przez `log_result`” |
| `ChatOrchestrator._execute_single_tool` | `source_persona_id = None` gdy `persona.type == "team_lead"` |
| `ResultsService.log_batch_from_agent` | sygnatura `source_persona_id: str \| None` |

Dlaczego `NULL`, a nie pseudo-persona: `TEAM_LEAD_PERSONA_ID` to `__team_lead__` (nie UUID), a `results.source_persona_id` ma FK na `personas(id)` — insert z tym stringiem wywaliłby się na typie/FK. `NULL` jest już dopuszczony schematem (`0001_init.sql:360`) i oznacza „agent bez persony”, co dla kierownika jest semantycznie poprawne. UI `/results` nie wymaga persony do wyświetlenia wpisu.

## Poza zakresem

- Bottom nav (Czat/Plan/Wyniki) — nadal odłożone.
- Zmiana kategorii wyników / migracja DB — brak.
- `log_result` dla `consult_persona` backstage — działa jak dziś.
- Edycja/usuwanie wyników przez Goata (tylko zapis).
