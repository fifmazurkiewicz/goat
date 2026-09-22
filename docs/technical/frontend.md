# Frontend architecture

Vite + React + TypeScript + Tailwind + shadcn/ui, hosted on Vercel (Hobby — 2–5 user scale, non-commercial/test use).

## 1. Routing

```
/login                → public, single "Sign in with Google" button (Supabase Auth, no magic link)
/onboarding           → protected (auth), gallery of 6 persona templates as the first screen
/personas             → protected (auth)
/chat, /chat/:sessionId → protected (auth) — 'persona' sessions (1:1) and 'general' (auto-routing, ADR-13)
/plans                → protected (auth)
/results              → protected (auth)
/profile              → protected (auth) — preview/edit `user_profile` (ADR-11); main filling path still via chat
/settings             → protected (auth) — nickname (+ Save nickname), theme, logout, exercise catalog (ADR-14, ADR-15)
/admin                → protected (auth + is_admin + is_approved); bootstrap: exclusively fmazurkiewicz@gmail.com
…
```

Unapproved accounts (`GET /account` → `is_approved=false`) stay inside the authenticated shell but see only the waiting screen (ADR-22): no nav, no personas/chat/admin. Poll every 15s; **Sprawdź status** / **Wyloguj**.

**Route guard "min. 1 active persona" for `/chat` and `/plans` — DECISION: deferred, doesn't block the first iteration.** Only implement when the core flow (personas → chat → results → plan) works end-to-end. When added: in the route loader (not in the page component, to avoid a flash before redirect), the condition read from `usePersonaStore` (shared with the onboarding gallery, not duplicated fetch).

## 2. State management — zustand / TanStack Query split

**Zustand — client/UI state, global:**
- `useAuthStore` — `user`, `session` (Supabase), `isAdmin`.
- `usePersonaStore` — persona list, `activePersonaId`, computed `hasActivePersona`.
- `usePlanGenerationStore` — **mounted in the app shell/root layout**, not in `/plans`. State `{status: 'idle'|'generating'|'ready'|'partial_ready'|'error', jobId, startedAt, phase, breakdown}`. Restores state from `localStorage` (`jobId`) on app start so a job survives closing the tab. It consumes authenticated plan-job SSE and falls back to REST after a stream failure; a compact app-wide indicator remains visible while the user navigates to Results or another screen.
- `useUsageLimitsStore` — refreshed on 429 or on usage headers in API responses. Powers the proactive "90% of limit" badge.

**TanStack Query — server state:** persona CRUD, results, message history, plans. Don't mix with zustand — server state has its own needs (cache, invalidation, refetch, loading/error states) that TanStack Query solves for free.

After receiving `tool_result` in the chat window: `queryClient.invalidateQueries(['results'])` globally — so `/results` shows fresh data after navigating from chat without a manual refresh.

**Cold-start lamp (ADR-19):** `GET /api/health` only during the wake-up window (not
`refetchInterval`, not ping on `/login` or background tab). Lamp next to "Coach" **only**
when 200 doesn't come back for ≥ 2 s; after 200 it disappears, invalidates remaining queries and **falls silent**, so
Render can sleep. Hover/tap = short text. Details:
[`../superpowers/specs/2026-08-16-api-status-lamp-design.md`](../superpowers/specs/2026-08-16-api-status-lamp-design.md).

## 3. SSE on the client side

`fetch` + `ReadableStream`, **not** `EventSource` (doesn't support POST with body nor the `Authorization` header).

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

Discriminated union: `type ChatStreamEvent = {type:'token', text:string} | {type:'tool_call_start', ...} | {type:'tool_result', ...} | {type:'done'} | {type:'error', message:string}`.

- **Cancel:** `AbortController` in the `useChatStream` hook, `abort()` in `useEffect` cleanup (navigation aborts the stream).
- **Reconnect: none in MVP (conscious debt).** Network error mid-stream → partial answer + "Connection lost" message + "Resend" (`POST .../message` with `retry: true` — the backend doesn't insert the same user message twice if the last `role=user` has identical content). Retry is for an **orphaned** turn (DB `turn_in_progress` after a kill / dropped SSE with no live producer). A still-running in-process turn returns **409**; the client must wait or call cancel, not start a second producer.
- **JWT expiry mid-stream** (401 mid-way) → readable "Session expired, sign in again" message, not a silent cut-off.
- Optimistic user-message addition (skipped on `retry`), streamed token append via batching (`requestAnimationFrame`/debounce 16–30 ms) — no re-render on every token.
- `aria-live="polite"` on the streaming assistant message container (not on the whole list) — accessibility for screen readers.

## 4. Components — `/chat`

```
ChatLayout (smart) — drawer open/closed (localStorage), URL sync sessionId;
│                    AppShell `h-dvh` + `--app-height` (visualViewport) + `min-h-0`.
│                    On `/chat` `main` = `overflow-hidden` (no page-scroll).
│                    Scroll only in MessageList; "Send" field always in viewport.
│                    Composer: `env(safe-area-inset-bottom)` + min. 44px.
├─ PersonaSessionDrawer (smart) — collapsible from the start (Sheet from shadcn on mobile)
│  └─ SessionListItem (dumb) — persona avatar/color (strong visual coding, not text only)
├─ ChatSessionsScreen (dumb) — MOBILE: `/chat` without `:sessionId` = full-screen conversation list
│  (same drawer without `Sheet`); desktop stays with the empty state "Select a conversation"
├─ ChatHeader (dumb) — session title; on mobile hamburger + "New conversation"; no copy /slug
├─ ChatWindow (smart) — chat state; SSE via global `useChatTurnRunner` in AppShell (turn in background)
│  ├─ MessageList (dumb) — bottom anchor (`chat-history-end`); no virtualization (MVP)
│  │  ├─ MessageBubble (dumb) — in 'general' session persona_label header (trainer or
│  │  │  **Goat · Team Lead** when `persona_id=null` — `isTeamLeadAssistantMessage`)
│  │  │  (context already known from ChatHeader). **Assistant** body rendered as Markdown
│  │  │  (`react-markdown`, no raw HTML). History UI filters `role=tool` and empty
│  │  │  `assistant` (tool_calls only) — raw tool JSONs stay in DB for LLM, not in bubble.
│  │  ├─ StreamingStatusLine (dumb) — single "persona + action" line during stream quiet
│  │  │  (routing / thinking / `tool_call_start`); PL map in `lib/chat-status.ts`; disappears on
│  │  │  first `token`. Start: general → "Picking a trainer…", persona → "Preparing…".
│  │  └─ ToolResultChip (dumb) — inline chip from `tool_result` (`tool_name`/`summary`/`success` fields)
│  │     in real time; after history refresh chip disappears (result visible in `/results` / profile)
│  │  └─ ConsultDetails (dumb, 2026-08-22) — expandable preview of Goat's consultation under his
│  │     message: `{personaLabel, question, answer}` from `consultDetails`; live via SSE
│  │     `consult_detail`, history from pairing `tool_calls`↔`role='tool'` (`visibleChatMessages`);
│  │     collapsed by default; this is not a separate trainer message (ADR-17 untouched)
│  └─ ChatInput (dumb) — disabled during stream and on 429; in 'general' session listens for
│     "/" at start of content → PersonaSlashAutocomplete (dropdown with avatar + name of
│     active personas, filtered by further typing; Enter/click inserts `/{slug} `) — raw
│     `/slug` syntax without hints is practically undiscoverable for a non-technical user
```

### 4a. Entering `/chat` — mobile vs desktop (since 2026-08-17)

| Context | Behavior |
|---|---|
| Mobile, `/chat` without session, first app entry, conversations exist | `navigate(/chat/<newest>, {replace:true})` — `latestSessionId()` by `updated_at` |
| Mobile, `/chat` after returning from conversation (or after deleting a session) | `ChatSessionsScreen` — conversation list; **without** another redirect (guard `useRef`) |
| Mobile, no conversations | list with "No conversations" + CTA "New conversation" |
| Desktop | as before: fixed drawer + empty state, zero redirects |

Previously the mobile list lived only in a closed `Sheet`, whose trigger (hamburger) was
in `ChatHeader` rendered only for an active session — the user had to create a new conversation to
see the history. Spec:
[2026-08-17](../superpowers/specs/2026-08-17-mobile-history-and-goat-log-result-design.md).

### 4b. New session — mode selection

"+ New conversation" opens a short choice: "General conversation" (auto-routing, `persona_id: null`) vs
selecting a specific persona from the list of active ones (1:1, as before) — `POST /chat/sessions {persona_id}`.

## 5. Components — `/plans`

```
PlansPage (smart) — activeMonth/activeDate from URL search params (linkable)
├─ CalendarViewSwitcher (smart) — Week/Month toggle on every breakpoint; default week on phone / month on desktop
│  ├─ WeekAgendaView (dumb) — phone default, custom (date-fns), not grid
│  └─ MonthGridView (dumb) — available on phone and desktop, react-day-picker / shadcn Calendar
├─ DayPanel (smart, responsive) — Sheet (bottom mobile / side desktop) from shadcn, one component, different `side`
│  ├─ PlanItemTable (dumb) — generic {title, columns, rows, notes} renderer
│  └─ ActualResultsPanel (dumb) — NEW: "Completed" — results logged that day next to "Planned"
│     (adherence tracking — plan vs results comparison, simple juxtaposition, no complex analytics in MVP)
├─ GeneratePlanCTA / EmptyState (dumb)
└─ PlanGenerationBanner (dumb) — reads global usePlanGenerationStore, does NOT do its own polling
```

`react-day-picker`/shadcn `Calendar` **only** for `MonthGridView` — there's no built-in week/agenda view, so `WeekAgendaView` (default on mobile) is custom-built with `date-fns` independently of the month-library choice. The Tydzień/Miesiąc switcher is visible on phones; `resolveCalendarView` keeps week as the mobile default until the user picks a view. `FullCalendar`/`react-big-calendar` — overkill, not recommended.

`PlansPage` **does not** initiate generation-status polling — it reads the result from `usePlanGenerationStore` (app shell) and renders success/partial/error for the selected day/month.

## 6. Charts in `/results`

**New feature (MVP):** per category, line chart of values over time (`logged_date` on X axis), filtered by `metric` — e.g. body weight trend, weight progression in a given exercise (bench press 1RM), running times. Library: **`recharts`** via the ready-made `Chart` shadcn/ui component (consistent styling with the rest of the UI, less code than raw recharts). Data from the existing `GET /results?category=&metric=` (the `results_user_category_metric_date` index in the DB supports these queries) — no schema change.

**Category tabs are not a fixed list of sports.** Built from the user's active personas (`resultCategoryTabsFromPersonas`) **and** categories that already have entries in the DB: e.g. `personal_trainer`/`motor_coach` → **Training** (`strength`), `dietitian` → Diet, `badminton_coach` → Badminton. This way a result saved by the agent as `triathlon`/`custom` doesn't disappear from the UI. Logo/name **Coach** in app shell → `/chat`.

## 7. Persona edit form

React Hook Form + Zod (`zodResolver`). Sections: basic data / **"How it should behave"** (`system_prompt` — style and scope of help; no medical content) / day structure as "advanced" (`Accordion`). Doctor/medication/red flags rules are in `app_private` + preamble — the UI informs that they are fixed. `persona_constraints` not present in the form.

Column editor: UI keeps a `{ name }[]` list in the form; on save maps to the API contract `template_overrides: { columns: string[] }` (per `resolve_persona_columns` in the backend). List editable via `useFieldArray` (name + ↑/↓ + delete + "+ Add column"). Zod validation: min. 1 column, max ~8, unique names, `custom_result_category` required conditionally (`superRefine`) for `type==='custom'`. On validation errors — toast + messages next to fields (incl. submit button can't "go silent").

## 7a. `/settings` — account, theme, logout, exercise catalog (ADR-14, ADR-15; amended 2026-09-07)

```
SettingsPage (smart)
├─ AccountSettingsCard (dumb) — nickname (input + "Save nickname" button, PATCH /api/v1/account)
│  + light/dark theme toggle (`useThemeStore`, localStorage only, ADR-15);
│  + "Wyloguj" (`supabase.auth.signOut` + `useAuthStore.signOut` + query cache clear;
│    `ProtectedRoute` then sends the user to `/login`);
│  `is_admin` from GET /account → `useAuthStore` (Admin tab in shell)
└─ ExerciseCatalog (smart) — ~873 entries after free-exercise-db import (Unlicense),
   PL content (LLM translation when generating seed 0013), `name_en` for matchers.
   Idle (empty query): 3 random from pool (category narrows the pool) + "Show other";
   full list only after typing a phrase. Random pick: `lib/exercise-catalog.ts`.
   ├─ ExerciseSearchBar (dumb) — search field (PL and EN via `name_en`) + category Select
   │  with grouping (Muscle groups / Workout type — chips don't scale to ~24 categories)
   └─ ExerciseGrid (dumb) — card = Link to `/exercises/:slug` (dialog removed),
      `grid-cols-1` <768px / `grid-cols-3` desktop, photo `loading="lazy"` +
      `decoding="async"`, 3:2 ratio (source 850×567), description `line-clamp-2`
```

**Detail page `/exercises/:slug`** (`ExerciseDetailPage`) — shared between catalog
and clickable names in plans (`PlanItemTable` links the first column matched by
`lib/exercise-matcher.ts`: PL/EN normalization + contains fallback). Data from cache
`useExercises` (staleTime 1 h) — no separate detail endpoint.

Data from `GET /exercises` (TanStack Query, long `staleTime` — reference content changes only
on deploy of a new migration) — filtering by category/query done **on the client side**:
at ~870 entries still cheap (`useMemo` + `useDeferredValue`); list payload
(~0.7 MB raw JSON, PL instructions) compressed by `GZipMiddleware`. No-pagination condition:
lazy-loading images + gzip; split list/detail deferred until a real problem.

## 8. Types — `openapi-typescript` from the start

Generated from FastAPI's `/openapi.json` (`npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts`) **from the first week of backend implementation**, not deferred. Cheap (one npm script), eliminates type drift on the first backend field change. SSE event types defined manually (OpenAPI doesn't describe the stream) — the only conscious exception.

## 9. Tests

Vitest + React Testing Library. Priority: SSE parser (`parseSseEvent`) > persona form (Zod validation) > `usePlanGenerationStore` state transitions > `PlanItemTable` edge cases (0 rows, mismatched length). No E2E (Playwright) at MVP start.

## 10. Handling 429

The limit is a budget in USD per account (`profiles.usage_budget_usd`, $10 default — ADR-16), not a subscription
plan. Inline message with the specific spent amount / limit and the period renewal date (not
a generic toast), block actions causing further 429 (graying out the input/button), proactive
"90% of budget" badge. **No** fake "Upgrade to Pro" CTA (MVP has no paid plans) — neutral
"Ask administrator to increase budget" link.

## 11. Mobile — `/personas`, `/results`, `/admin` (UX audit additions)

Sections 4–5 address mobile for `/chat` and `/plans` explicitly. For other pages:

- **`/personas`, community, exercise catalog** — `grid-cols-3` (desktop) grids collapse to
  `grid-cols-1` <768px; persona prompt/exercise description as `line-clamp-2` instead of full
  `text-align: justify` (unreadable in a narrow card on a small screen).
- **"Add persona" dialog** — `Sheet` (bottom, full height) on mobile instead of centered
  `Dialog`; persona template grid `grid-cols-1` instead of `grid-cols-2`.
- **`PlanItemTable` (training/diet, up to 5 columns)** — on mobile rendered as a card-per-row
  list (column label + value, like a definition list) instead of horizontal scroll in
  `<table>` — horizontal scroll in a table is poor touch UX with 5 columns.
  `PlanItemTable` accepts `variant: 'table' | 'cards'` prop, selected by breakpoint
  (matchMedia), the data rendering logic (columns/rows) stays shared.
- **`/results` and `/admin` tables** — first column `sticky left-0` + horizontal scroll for
  the rest (not card-layout — tabular data with many numeric columns is more readable
  as a table even with scroll, unlike `PlanItemTable` where columns have variable, text content).
  Actions in `/results` have touch target ≥44px.
- **Viewport (ADR-18):** `viewport-fit=cover`, `h-dvh` + `--app-height` from `visualViewport`
  (iOS/Android keyboard). Safe area: header `pt-[env(safe-area-inset-top)]`, pages and
  composer `pb-[env(safe-area-inset-bottom)]`. Page gutter: `PAGE_SHELL_CLASS` (`py-6` on
  phone, `md:py-10`). Touch target min. 44px (`min-h-11`) in nav, composer, tabs,
  catalog chips and plan buttons. Input/textarea: `text-base md:text-sm` (no iOS zoom
  on focus). `useIsMobile`: `(max-width: 767px), (max-height: 500px)` — iPhone
  landscape gets Sheet (not a centered Dialog). Plan week/month is a user toggle; default remains week.
  `ResponsiveDialog`: single scroll, footer `shrink-0` + safe area.
- **Navigation:** horizontal scroll of the top bar (6 positions) stays in MVP; bottom nav (Chat /
  Plan / Results) — consciously deferred (variant B of UX audit 2026-08-16).
- **Pull-to-refresh (2026-08-22):** "pull-down" gesture refreshes data on ALL screens
  (mobile, touch only — `pointerType === "touch"`). `PullToRefresh` in AppShell
  around `<Outlet />` + `usePullToRefresh` (72 px threshold, distance damping, "scroller at top"
  detection through ancestor chain). Soft refresh = `queryClient.invalidateQueries()`
  (no hard reload, SSE stream doesn't die). `overscroll-behavior-y: none` on html/body
  disables Chrome Android's native PTR. Spec:
  [2026-08-22-pull-to-refresh-design.md](../superpowers/specs/2026-08-22-pull-to-refresh-design.md).
