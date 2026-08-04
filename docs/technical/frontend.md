# Architektura frontendu

Vite + React + TypeScript + Tailwind + shadcn/ui, hosting Vercel (Hobby — skala 2-5 userów, użytek niekomercyjny/testowy).

## 1. Routing

```
/login                → publiczna, jeden przycisk "Zaloguj się przez Google" (Supabase Auth, bez magic linka)
/onboarding           → chroniona (auth), galeria 6 szablonów person jako pierwszy ekran
/personas             → chroniona (auth)
/chat, /chat/:sessionId → chroniona (auth) — sesje 'persona' (1:1) i 'general' (auto-routing, ADR-13)
/plans                → chroniona (auth)
/results              → chroniona (auth)
/settings             → chroniona (auth) — nick (+ Zapisz nick), motyw, katalog ćwiczeń (ADR-14, ADR-15)
/admin                → chroniona (auth + is_admin); bootstrap: wyłącznie fmazurkiewicz@gmail.com
…
```

**Route guard "min. 1 aktywna persona" dla `/chat` i `/plans` — DECYZJA: odłożony, nie blokuje pierwszej iteracji.** Zaimplementować dopiero gdy core flow (persony → czat → wyniki → plan) działa end-to-end. Gdy zostanie dodany: w loaderze route'u (nie w komponencie strony, żeby uniknąć flasha przed redirectem), warunek czytany z `usePersonaStore` (współdzielony z galerią onboardingu, nie duplikowany fetch).

## 2. State management — rozdział zustand / TanStack Query

**Zustand — stan kliencki/UI, globalny:**
- `useAuthStore` — `user`, `session` (Supabase), `isAdmin`.
- `usePersonaStore` — lista person, `activePersonaId`, computed `hasActivePersona`.
- `usePlanGenerationStore` — **mountowany w app shell/root layout**, nie w `/plans`. Stan `{status: 'idle'|'generating'|'ready'|'partial_ready'|'error', jobId, startedAt, breakdown}`. Odtwarza stan z `localStorage` (`jobId`) przy starcie appki, żeby polling przetrwał zamknięcie karty. Sam odpala toast przy zmianie statusu (side-effect w miejscu gdzie żyje polling, nie w komponencie).
- `useUsageLimitsStore` — odświeżany po 429 lub po nagłówkach usage w odpowiedzi API. Zasila proaktywny badge "90% limitu".

**TanStack Query — server state:** CRUD person, results, historia wiadomości, plany. Nie mieszać z zustand — server state ma własne potrzeby (cache, invalidacja, refetch, loading/error states), które TanStack Query rozwiązuje za darmo.

Po odebraniu `tool_result` w oknie czatu: `queryClient.invalidateQueries(['results'])` globalnie — żeby `/results` pokazywał świeże dane po przejściu z czatu bez ręcznego refresh.

## 3. SSE po stronie klienta

`fetch` + `ReadableStream`, **nie** `EventSource` (nie wspiera POST z body ani nagłówka `Authorization`).

```typescript
async function* streamChatMessage(sessionId: string, body: SendMessageBody, signal: AbortSignal) {
  const res = await fetch(`/api/chat/sessions/${sessionId}/message`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw await toApiError(res);

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    const chunks = buffer.split('\n\n');
    buffer = chunks.pop() ?? '';
    for (const chunk of chunks) yield parseSseEvent(chunk);
  }
}
```

Dyskryminowany union: `type ChatStreamEvent = {type:'token', text:string} | {type:'tool_call_start', ...} | {type:'tool_result', ...} | {type:'done'} | {type:'error', message:string}`.

- **Anulowanie:** `AbortController` w `useChatStream` hooku, `abort()` w cleanupie `useEffect` (nawigacja przerywa stream).
- **Reconnect: brak w MVP (świadomy dług).** Błąd sieci w trakcie streamu → częściowa odpowiedź + komunikat "Połączenie przerwane" + "Wyślij ponownie" (`POST .../message` z `retry: true` — backend nie wstawia drugi raz tej samej wiadomości usera, jeśli ostatni `role=user` ma identyczną treść).
- **Wygaśnięcie JWT w trakcie streamu** (401 w połowie) → czytelny komunikat "Sesja wygasła, zaloguj się ponownie", nie ciche urwanie.
- Optymistyczne dodanie wiadomości usera (pomijane przy `retry`), strumieniowe append tokenów przez batchowanie (`requestAnimationFrame`/debounce 16-30ms) — nie re-render przy każdym tokenie.
- `aria-live="polite"` na kontenerze streamującej wiadomości asystenta (nie na całej liście) — accessibility dla czytników ekranu.

## 4. Komponenty — `/chat`

```
ChatLayout (smart) — drawer open/closed (localStorage), URL sync sessionId
├─ PersonaSessionDrawer (smart) — collapsible od startu (Sheet z shadcn na mobile)
│  └─ SessionListItem (dumb) — avatar/kolor persony (silne kodowanie wizualne, nie tylko tekst)
├─ ChatHeader (dumb) — avatar/kolor/nazwa aktywnej persony
├─ ChatWindow (smart) — JEDYNE miejsce otwierające/zamykające SSE (useChatStream hook)
│  ├─ MessageList (dumb, wirtualizowana przy długiej historii — @tanstack/react-virtual)
│  │  ├─ MessageBubble (dumb) — w sesji 'general' pokazuje nagłówek persona_label (z eventu
│  │  │  `persona_turn_start`, ADR-13) nad odpowiedzią; w sesji 'persona' nagłówek pomijany
│  │  │  (kontekst już wiadomy z ChatHeader). Historia UI filtruje `role=tool` i puste
│  │  │  `assistant` (tool_calls-only) — surowe JSON-y narzędzi zostają w DB dla LLM, nie w bubble.
│  │  └─ ToolResultChip (dumb) — inline chip z `tool_result` (pola `tool_name`/`summary`/`success`)
│  │     w czasie rzeczywistym; po odświeżeniu historii chip znika (wynik widać w `/results` / profilu)
│  └─ ChatInput (dumb) — disabled podczas streamu i przy 429; w sesji 'general' nasłuchuje na
│     wpisanie "/" na starcie treści → PersonaSlashAutocomplete (dropdown z avatarem + nazwą
│     aktywnych person, filtrowany po dalszym wpisywaniu; Enter/klik wstawia `/{slug} `) — surowa
│     składnia `/slug` bez podpowiedzi jest praktycznie nieodkrywalna dla nietechnicznego usera
```

### 4a. Nowa sesja — wybór trybu

"+ Nowa rozmowa" otwiera krótki wybór: "Ogólna rozmowa" (auto-routing, `persona_id: null`) vs
wybór konkretnej persony z listy aktywnych (1:1, jak dotychczas) — `POST /chat/sessions {persona_id}`.

## 5. Komponenty — `/plans`

```
PlansPage (smart) — activeMonth/activeDate z URL search params (linkowalne)
├─ CalendarViewSwitcher (smart) — Week/Month wg breakpointu (matchMedia) + ręczny override desktop
│  ├─ WeekAgendaView (dumb) — <768px DEFAULT, custom (date-fns), nie grid
│  └─ MonthGridView (dumb) — desktop opcja, react-day-picker / shadcn Calendar
├─ DayPanel (smart, responsywny) — Sheet(bottom mobile / side desktop) z shadcn, jeden komponent, różny `side`
│  ├─ PlanItemTable (dumb) — generyczny renderer {title, columns, rows, notes}
│  └─ ActualResultsPanel (dumb) — NOWE: "Zrealizowane" — results zalogowane tego dnia obok "Zaplanowane"
│     (adherence tracking — porównanie plan vs wyniki, prosta juxtapozycja, bez złożonej analityki w MVP)
├─ GeneratePlanCTA / EmptyState (dumb)
└─ PlanGenerationBanner (dumb) — czyta globalny usePlanGenerationStore, NIE robi własnego pollingu
```

`react-day-picker`/shadcn `Calendar` **tylko** dla `MonthGridView` — nie ma wbudowanego widoku tygodnia/agendy, więc `WeekAgendaView` (domyślny na mobile) buduje się custom z `date-fns` niezależnie od wyboru biblioteki miesiąca. `FullCalendar`/`react-big-calendar` — przeskalowane, nie polecane.

`PlansPage` **nie** inicjuje pollingu statusu generowania — czyta wynik z `usePlanGenerationStore` (app shell) i renderuje sukces/partial/błąd dla wybranego dnia/miesiąca.

## 6. Wykresy w `/results`

**Nowa funkcja (MVP):** per kategoria, wykres liniowy wartości w czasie (`logged_date` na osi X), filtrowany po `metric` — np. trend wagi ciała, progresja ciężaru w danym ćwiczeniu (bench press 1RM), czasy biegowe. Biblioteka: **`recharts`** przez gotowy `Chart` komponent shadcn/ui (spójny styling z resztą UI, mniej kodu niż surowy recharts). Dane z istniejącego `GET /results?category=&metric=` (indeks `results_user_category_metric_date` w bazie wspiera te zapytania) — bez zmian schematu.

**Taby kategorii nie są stałą listą sportów.** Budowane z aktywnych person usera (`resultCategoryTabsFromPersonas`): np. `personal_trainer`/`motor_coach` → Siłownia, `dietitian` → Dieta, `badminton_coach` → Badminton. Brak persony triathlon/basen = brak tych tabów. Logo/nazwa **Coach** w app shell → `/chat`.

## 7. Formularz edycji persony

React Hook Form + Zod (`zodResolver`). Sekcje: podstawowe dane / **„Jak ma się zachowywać”** (`system_prompt` — styl i zakres pomocy; bez treści medycznych) / struktura dnia jako "zaawansowane" (`Accordion`). Reguły lekarz/leki/red flags są w `app_private` + preambule — UI informuje, że są stałe. `persona_constraints` nieobecne w formularzu.

Edytor kolumn: UI trzyma listę `{ name }[]` w formularzu; przy zapisie mapuje na kontrakt API `template_overrides: { columns: string[] }` (zgodnie z `resolve_persona_columns` w backendzie). Lista edytowalna przez `useFieldArray` (nazwa + ↑/↓ + usuń + "+ Dodaj kolumnę"). Walidacja Zod: min. 1 kolumna, max ~8, unikalne nazwy, `custom_result_category` wymagane warunkowo (`superRefine`) dla `type==='custom'`. Przy błędach walidacji — toast + komunikaty przy polach (w tym przycisk submit nie może „milczeć”).

## 7a. `/settings` — konto, motyw, katalog ćwiczeń (ADR-14, ADR-15)

```
SettingsPage (smart)
├─ AccountSettingsCard (dumb) — nick (input + przycisk „Zapisz nick”, PATCH /api/v1/account)
│  + przełącznik motywu jasny/ciemny (`useThemeStore`, tylko localStorage, ADR-15);
│  `is_admin` z GET /account → `useAuthStore` (zakładka Admin w shellu)
└─ ExerciseCatalog (smart)
   ├─ ExerciseSearchBar (dumb) — pole szukania + filter-chipy kategorii, `overflow-x-auto`
   │  na mobile (NIE flex-wrap — wrap zajmuje zbyt dużo wysokości ekranu przed treścią)
   ├─ ExerciseGrid (dumb) — `grid-cols-1` <768px / `grid-cols-3` desktop, karta ze zdjęciem
   │  (`AspectRatio` shadcn, placeholder gdy `photo_path` NULL), nazwą, poziomem, kategoriami,
   │  opisem skróconym (`line-clamp-2`, nie pełny `text-align: justify` na mobile — nieczytelne
   │  w wąskiej karcie)
   └─ ExerciseDetailDialog (dumb, `Sheet` na mobile / `Dialog` desktop) — zdjęcie pełne,
      "Wykonanie" (`detail_full`), "Częste błędy" (`common_mistakes`)
```

Dane z `GET /exercises` (TanStack Query, `staleTime` długi — treść referencyjna zmienia się
wyłącznie przy deployu nowej migracji) — filtrowanie po kategorii/query robione **po stronie
klienta** (katalog rzędu kilkudziesięciu pozycji, brak potrzeby round-tripu przy każdej zmianie
filtra).

## 8. Typy — `openapi-typescript` od startu

Generowane z `/openapi.json` FastAPI (`npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts`) **od pierwszego tygodnia implementacji backendu**, nie odkładane. Tanie (jeden skrypt npm), eliminuje rozjazd typów przy pierwszej zmianie pola backendu. Typy SSE eventów definiowane ręcznie (OpenAPI nie opisuje strumienia) — jedyny świadomy wyjątek.

## 9. Testy

Vitest + React Testing Library. Priorytet: parser SSE (`parseSseEvent`) > formularz persony (walidacja Zod) > `usePlanGenerationStore` przejścia stanu > `PlanItemTable` edge cases (0 wierszy, niedopasowana długość). Bez E2E (Playwright) na start MVP.

## 10. Obsługa limitu 429

Limit to budżet w USD per konto (`profiles.usage_budget_usd`, domyślnie $10 — ADR-16), nie plan
subskrypcyjny. Komunikat inline z konkretną kwotą wykorzystaną/limitem i datą odnowienia okresu (nie
generyczny toast), blokada akcji powodującej kolejne 429 (wyszarzenie inputu/przycisku), proaktywny
badge "90% budżetu". **Bez** fałszywego CTA "Upgrade to Pro" (MVP nie ma płatnych planów) — neutralny
link "Poproś administratora o zwiększenie budżetu".

## 11. Mobile — `/personas`, `/results`, `/admin` (uzupełnienie audytu UX)

Sekcje 4-5 adresują mobile dla `/chat` i `/plans` explicite. Dla pozostałych stron:

- **`/personas`, community, katalog ćwiczeń** — siatki `grid-cols-3` (desktop) kolapsują do
  `grid-cols-1` <768px; opis promptu/ćwiczenia jako `line-clamp-2` zamiast pełnego
  `text-align: justify` (nieczytelne w wąskiej karcie na małym ekranie).
- **Dialog "Dodaj personę"** — `Sheet` (bottom, pełna wysokość) na mobile zamiast `Dialog`
  wyśrodkowanego; siatka szablonów person `grid-cols-1` zamiast `grid-cols-2`.
- **`PlanItemTable` (trening/dieta, do 5 kolumn)** — na mobile renderowana jako lista
  card-per-row (etykieta kolumny + wartość, jak definition list) zamiast poziomego scrolla w
  `<table>` — scroll horyzontalny w tabeli to słaby touch UX przy 5 kolumnach.
  `PlanItemTable` przyjmuje prop `variant: 'table' | 'cards'`, wybierany przez breakpoint
  (matchMedia), sama logika renderowania danych (kolumny/wiersze) pozostaje wspólna.
- **Tabele `/results` i `/admin`** — pierwsza kolumna `sticky left-0` + poziomy scroll dla
  reszty (nie card-layout — dane tabelaryczne z wieloma numerycznymi kolumnami czytelniejsze
  w formie tabeli nawet przy scrollu, w odróżnieniu od `PlanItemTable` gdzie kolumny mają
  zmienną, tekstową treść).
