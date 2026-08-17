# Plan roboczy: historia rozmów na mobile + `log_result` u Goata

**Data:** 2026-08-17
**Spec:** [docs/superpowers/specs/2026-08-17-mobile-history-and-goat-log-result-design.md](../../docs/superpowers/specs/2026-08-17-mobile-history-and-goat-log-result-design.md)

## Problem (zgłoszenie usera)

1. Na telefonie wejście na `/chat` (bez `:sessionId`) pokazuje empty state „Wybierz rozmowę z listy albo zacznij nową”. Lista rozmów żyje wyłącznie w zamkniętym `Sheet`, a jedyny trigger (hamburger) jest w `ChatHeader`, renderowanym tylko gdy istnieje aktywna sesja → user musi kliknąć „Nowa rozmowa”, żeby dostać hamburger i zobaczyć historię.
2. Goat w czacie nie może zapisać zaraportowanych wyników do bazy — `log_result` jest świadomie wyłączone dla `team_lead` (`TEAM_LEAD_CHAT_TOOL_NAMES`, prompt „Nie wołaj log_result”), a `consult_persona` po zmianie z 2026-08-17 wywoływany jest rzadko, więc nikt nie zapisuje.

## Decyzje

| Data | Decyzja | Dlaczego |
|------|---------|----------|
| 2026-08-17 | Mobile wariant **C**: `/chat` bez sesji = pełnoekranowa lista rozmów **oraz** auto-wejście w ostatnią rozmowę przy starcie | Wybór usera; wzorzec messengera (lista ↔ wątek) + szybki powrót do rozmowy |
| 2026-08-17 | Auto-wejście tylko raz na wejście do appki i tylko na `/chat` bez `:sessionId`; nie nadpisuje ręcznego powrotu do listy | Inaczej user nie mógłby zostać na liście (redirect-loop UX) |
| 2026-08-17 | Wyniki wariant **A**: Goat dostaje `log_result` | Goat ma już ostateczny głos nad planem; brak prawa zapisu wyniku = niespójność (user raportuje trening Goatowi, nie trenerowi) |
| 2026-08-17 | `source_persona_id = NULL` dla wpisów Goata | `TEAM_LEAD_PERSONA_ID` = `__team_lead__` (nie UUID); kolumna `results.source_persona_id` jest nullable z FK na `personas` |
| 2026-08-17 | ADR-6/ADR-17 nowelizacja w docs (nie nowy ADR) | Zmiana granicy narzędzi istniejącej roli, nie nowa decyzja architektoniczna |

## Given / When / Then

- Given telefon i istniejące rozmowy, When user wchodzi na `/chat` bez `:sessionId` po raz pierwszy w sesji przeglądarki, Then trafia do ostatnio aktualizowanej rozmowy (bez klikania „Nowa rozmowa”).
- Given telefon, When user wraca z rozmowy na `/chat` (np. po usunięciu sesji lub z nawigacji), Then widzi pełnoekranową listę rozmów z „Nowa rozmowa”, bez ponownego auto-redirectu.
- Given brak jakichkolwiek rozmów, When user wchodzi na `/chat`, Then widzi empty state z CTA „Nowa rozmowa” (bez redirectu).
- Given desktop, When user wchodzi na `/chat`, Then zachowanie jak dziś (stały drawer + empty state), bez auto-redirectu.
- Given sesja `general` i user raportuje wynik treningu Goatowi, When Goat woła `log_result`, Then wpisy trafiają do `results` z `source='agent'` i `source_persona_id=NULL`, a FE pokazuje chip „Wynik”.
- Given trener (slash/1:1), When woła `log_result`, Then zapis jak dziś z `source_persona_id` = jego UUID (bez regresji).

## Status

W trakcie (2026-08-17).
