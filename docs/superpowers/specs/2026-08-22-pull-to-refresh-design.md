# Design: Pull-to-refresh (mobile) w całej aplikacji

**Data:** 2026-08-22
**Status:** zaakceptowany (do implementacji)
**Kontekst:** user na telefonie odruchowo przeciąga ekran w dół, żeby odświeżyć stronę — oczekuje tego samego wzorca w appce.

## Cel / zakres

Gest „pociągnięcie w dół" odświeża dane bieżącego ekranu na urządzeniach dotykowych, **na wszystkich ekranach** appki (czat, persony, plany, wyniki, profil, ustawienia). Odświeżenie = **soft refresh** (React Query `invalidateQueries()`), nie twarde przeładowanie strony. Desktop/mysz — bez zmian zachowania.

## Wymagania (Given / When / Then)

### GWT-1 — pociągnięcie odświeża

**Given** mobile, dowolny ekran, wszystkie scrollery pod palcem na pozycji 0 (`scrollTop === 0`)
**When** user pociągnie w dół ≥ próg (~72 px) i puści
**Then** pojawia się wskaźnik (spinner), odpalane jest `queryClient.invalidateQueries()` (wszystkie aktywne query)
**And** spinner kręci się do zakończenia refetchu, potem znika

### GWT-2 — pociągnięcie poniżej progu

**When** user pociągnie w dół < próg i puści
**Then** brak odświeżenia, wskaźnik sprężyście wraca do 0

### GWT-3 — scroll w dół historii nie triggeruje

**Given** MessageList / lista sesji / inny wewnętrzny scroller przewinięty (`scrollTop > 0`)
**When** user pociąga palcem w dół
**Then** to zwykły scroll treści, wskaźnik się nie pojawia

### GWT-4 — desktop bez reakcji

**Given** desktop, drag myszą przy scrollTop=0
**Then** brak wskaźnika i brak odświeżania (nasłuch tylko `pointerType === "touch"`)

### GWT-5 — brak podwójnego odpalenia

**Given** odświeżanie w toku
**When** kolejne pociągnięcie
**Then** ignorowane aż do ukończenia bieżącego cyklu

### GWT-6 — poziomy ruch nie pulluje

**When** gest głównie poziomy (`|dx| > |dy|`)
**Then** brak reakcji (swipe poziomy np. po nawigacji tabami)

## Architektura

| Element | Plik | Rola |
|---|---|---|
| Hook | `frontend/src/hooks/usePullToRefresh.ts` | pointer events (`pointerdown/move/up`, `pointerType === "touch"`), dystans z tłumieniem, detekcja „scroller na górze" (łańcuch `parentElement` od `event.target`), stan `pullDistance`/`isRefreshing` |
| Wrapper | `frontend/src/components/layout/PullToRefresh.tsx` | otacza `<Outlet />` w AppShell; renderuje wskaźnik wysuwany nad treścią wg `pullDistance` (transform, bez layout shift); próg 72 px |
| Montaż | `AppShell.tsx` | `<PullToRefresh onRefresh={...}>` wokół `<Outlet />` — jeden punkt, działa wszędzie |
| CSS | `index.css` | `overscroll-behavior-y: none` na `html/body` — wyłącza natywny pull-to-refresh Chrome Android, który konkurowałby z naszym |

### Detekcja „można pullować"

Przy `pointermove`: idziemy od `event.target` w górę DOM; jeśli **którykolwiek** przodek ma `overflow-y: auto|scroll` **i** `scrollTop > 0` → gest anulowany (to scroll treści). Dzięki temu działa poprawnie i w trybie czat (`main.overflow-hidden`, wewnętrzne scrollery: MessageList, lista sesji), i na stronach (`main.overflow-y-auto`).

### Odświeżanie danych

Jedno uniwersalne wywołanie: `queryClient.invalidateQueries()` bez filtrów → refetch wszystkich aktywnych query React Query (wiadomości, sesje, persony, wyniki, plany, usage). Stan UI (rozwinięcia, zaznaczenia, input) zostaje nietknięty; stream SSE w toku żyje w store (nie w query) i **nie jest przerywany**.

## Błędy / edge case'y

| Przypadek | Zachowanie |
|---|---|
| Refetch rzuca błędem | React Query standardowo (dane stare zostają); spinner znika po rozstrzygnięciu (`Promise.allSettled` semantyka przez `refetchQueries`) |
| Gest podczas `isRefreshing` | ignorowany (GWT-5) |
| `pointerleave`/`pointercancel` w trakcie | traktowane jak puszczenie poniżej progu — powrót sprężynowy |
| Rotacja / zmiana viewport w trakcie gestu | reset dystansu |

## Poza zakresem

- Obsługa drags myszą na desktopie.
- Indywidualne progi/etykiety per ekran.
- Pull-to-refresh list w środku strony (np. pojedynczej karty) — odświeżamy globalnie.

## Dokumenty do aktualizacji

- `docs/technical/frontend.md` — sekcja o PTR (hook + wrapper + próg + ograniczenie touch).
- `AGENTS.md` — jedno zdanie w faktach (mobile UX).
