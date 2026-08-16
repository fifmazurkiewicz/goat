# Design: Lampka statusu API (cold start Render)

**Data:** 2026-08-16  
**Status:** wdrożone (2026-08-16)  
**Powiązane:** ADR-19 · [`docs/technical/frontend.md`](../../technical/frontend.md) · [`docs/technical/devops.md`](../../technical/devops.md)

## Problem

Frontend na Vercelu wstaje od razu. Backend na Render Free usypia po ~15 min bezczynności; pierwsze requesty do API potrafią wisieć 30–60 s. User widzi puste listy / „Failed to fetch” i odświeża stronę, bo nie wie, że serwer się budzi.

## Cel

Mała **lampka tylko gdy czekamy na API**. Hover (desktop) albo tap (telefon) tłumaczy, co się dzieje. Po wybudzeniu lampka **znika**. Requesty TanStack Query same się ponawiają — bez F5.

**Backend ma móc usnąć.** Lampka nie jest heartbeatem. Żadnego cyklicznego `/api/health`, gdy aplikacja już działa albo karta jest w tle.

## Stany

| Stan UI | Kiedy | Lampka | Tekst (hover / tap) |
|---------|--------|--------|---------------------|
| `hidden` | API odpowiada **albo** nic właśnie nie czekamy | brak | — |
| `waking` | realny request (albo sonda wybudzania) wisi ≥ 2 s | bursztyn, puls | Budzimy aplikację, poczekaj chwilę. |
| `down` | nadal brak sukcesu po ~90 s | czerwień, bez pulsu | Nie możemy połączyć się z serwerem. Spróbujemy ponownie. |

Domyślnie nic nie widać (lokalnie i gdy Render już ciepły). Nie ma zielonej lampki „wszystko OK”.

## Sondowanie — twarde reguły

`GET {VITE_API_BASE_URL}/api/health` (publiczny, bez JWT; kontrakt bez zmian: `200` + `{"status":"ok"}`) wolno wysłać **wyłącznie** w oknie wybudzania:

1. **Start okna:** mount AppShell (albo błąd sieci w `apiFetch` / SSE, nie 4xx/5xx z JSON). Sam mount `/login` **nie** pinguje — Google OAuth nie potrzebuje Rendera; ping przy każdym otwarciu logowania by budził serwer bez potrzeby.
2. **W oknie:** timeout próby 8 s; kolejna próba co 4 s, **tylko** gdy karta jest widoczna (`document.visibilityState === "visible"`).
3. **Koniec okna (natychmiast stop, zero dalszych health):** pierwsze 200 **albo** ~90 s bez 200 **albo** karta schodzi w tło. Po `down` automat **nie** kręci się dalej; tap w lampkę = jedno nowe okno (znowu max ~90 s).
4. **Po 200:** lampka znika, `queryClient.invalidateQueries()` (poza health). Dopóki kolejne **rzeczywiste** requesty użytkownika przechodzą, **żadnego** `/api/health`.

Zakazane: `refetchInterval` gdy zdrowo; ping co N sekund „na wszelki wypadek”; keep-alive w tle; ping przy ukrytej karcie.

## UI

- Miejsce: header AppShell obok „Coach”. Na `/login` lampka tylko jeśli ta strona faktycznie czeka na API (dev-login), nie przy samym wejściu.
- Hit area ≥ 44px; kropka ~10px.
- Hover otwiera krótki tekst; tap/klik też. Nie ma bannera ani overlaya.
- `aria-label` = treść z tabeli; gdy lampka widoczna: `role="status"` / `aria-live="polite"`.

## Poza zakresem

- Overlay / banner / toast przy każdym błędzie.
- Zewnętrzny keep-alive (UptimeRobot, cron) i jakikolwiek ping, który trzyma Render bezczynnie przy życiu.
- Zmiana `/api/health` (zostaje liveness bez DB).
- Upgrade Render Free → Starter.

## Wymagania (Given / When / Then)

### GWT-1 — ciepły backend: cisza

**Given** pierwszy health (albo zwykły request AppShell) zwraca 200 w mniej niż 2 s  
**When** user jest w apce  
**Then** lampka nie jest renderowana  
**And** nie ma dalszych wywołań `/api/health`

### GWT-2 — cold start: lampka i tekst

**Given** AppShell czeka na API i nie ma 200 przez co najmniej 2 s  
**When** user patrzy na header  
**Then** widać bursztynową pulsującą lampkę  
**And** hover albo tap pokazuje „Budzimy aplikację, poczekaj chwilę.”

### GWT-3 — po wybudzeniu znika, dane wracają, pingi stop

**Given** lampka w stanie `waking`  
**When** health zwraca 200  
**Then** lampka znika  
**And** zapytania TanStack Query, które padły na timeout/sieć, są ponawiane bez odświeżania strony  
**And** frontend **nie** wysyła więcej `/api/health`, dopóki nie zacznie się nowe okno z GWT-6

### GWT-4 — długotrwała awaria: stop automatu

**Given** okno wybudzania trwa ~90 s bez 200  
**When** user tapnie lampkę  
**Then** kolor jest czerwony (bez pulsu)  
**And** tekst: „Nie możemy połączyć się z serwerem. Spróbujemy ponownie.”  
**And** automatyczne `/api/health` już nie idą  
**And** tap startuje **jedno** nowe okno wybudzania (znowu limit ~90 s)

### GWT-5 — login nie budzi Rendera sam z siebie

**Given** user jest na `/login` i nic nie wysyła do API  
**When** strona się montuje  
**Then** nie ma requestu `/api/health`  
**And** lampki nie widać

### GWT-6 — ponowny sen tylko po prawdziwym błędzie

**Given** API było OK, lampka ukryta, brak sondy  
**When** `apiFetch` / SSE kończy się błędem sieci (nie 4xx/5xx z JSON)  
**Then** startuje nowe okno wybudzania; po 2 s bez 200 lampka wraca w `waking`

### GWT-7 — karta w tle nie trzyma serwera

**Given** trwa okno wybudzania albo apka jest już „zdrowa”  
**When** karta jest w tle (`visibilityState !== "visible"`) albo user nic nie robi przez 15 min  
**Then** frontend nie wysyła `/api/health`  
**And** Render Free może usnąć
