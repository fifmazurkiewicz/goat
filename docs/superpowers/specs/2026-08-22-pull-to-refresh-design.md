# Design: Pull-to-refresh (mobile) across the whole app

**Date:** 2026-08-22
**Status:** accepted (for implementation)
**Context:** the user on the phone instinctively pulls the screen down to refresh the page — they expect the same pattern in the app.

## Goal / scope

The "pull down" gesture refreshes the data of the current screen on touch devices, **on all screens** of the app (chat, personas, plans, results, profile, settings). Refresh = **soft refresh** (React Query `invalidateQueries()`), not a hard page reload. Desktop/mouse — no behavior change.

## Requirements (Given / When / Then)

### GWT-1 — pull refreshes

**Given** mobile, any screen, all scrollers under the finger at position 0 (`scrollTop === 0`)
**When** the user pulls down ≥ threshold (~72 px) and releases
**Then** the indicator appears (spinner), `queryClient.invalidateQueries()` is fired (all active queries)
**And** the spinner spins until the refetch completes, then disappears

### GWT-2 — pull below the threshold

**When** the user pulls down < threshold and releases
**Then** no refresh, the indicator springs back to 0

### GWT-3 — scroll down history does not trigger

**Given** MessageList / session list / other inner scroller scrolled (`scrollTop > 0`)
**When** the user pulls down with their finger
**Then** that's normal content scrolling, the indicator does not appear

### GWT-4 — desktop does not react

**Given** desktop, mouse drag at scrollTop=0
**Then** no indicator and no refresh (listening only for `pointerType === "touch"`)

### GWT-5 — no double trigger

**Given** refresh in progress
**When** next pull
**Then** ignored until the current cycle completes

### GWT-6 — horizontal movement does not trigger pull

**When** the gesture is mostly horizontal (`|dx| > |dy|`)
**Then** no reaction (horizontal swipe e.g. across tab navigation)

## Architecture

| Element | File | Role |
|---|---|---|
| Hook | `frontend/src/hooks/usePullToRefresh.ts` | pointer events (`pointerdown/move/up`, `pointerType === "touch"`), damped distance, "scroller at top" detection (chain of `parentElement` from `event.target`), `pullDistance`/`isRefreshing` state |
| Wrapper | `frontend/src/components/layout/PullToRefresh.tsx` | wraps `<Outlet />` in AppShell; renders the indicator pulled out above the content by `pullDistance` (transform, no layout shift); 72 px threshold |
| Mount | `AppShell.tsx` | `<PullToRefresh onRefresh={...}>` around `<Outlet />` — one place, works everywhere |
| CSS | `index.css` | `overscroll-behavior-y: none` on `html/body` — disables Chrome Android's native pull-to-refresh, which would compete with ours |

### "Can pull" detection

On `pointermove`: walk up the DOM from `event.target`; if **any** ancestor has `overflow-y: auto|scroll` **and** `scrollTop > 0` → gesture cancelled (that's content scroll). Thanks to this it works correctly both in chat mode (`main.overflow-hidden`, inner scrollers: MessageList, session list), and on pages (`main.overflow-y-auto`).

### Data refresh

One universal call: `queryClient.invalidateQueries()` without filters → refetches all active React Query queries (messages, sessions, personas, results, plans, usage). UI state (expansions, selections, input) stays untouched; the SSE stream in progress lives in the store (not in the query) and **is not interrupted**.

## Errors / edge cases

| Case | Behavior |
|------|----------|
| Refetch throws | React Query standard (stale data remains); spinner disappears after resolution (`Promise.allSettled` semantics via `refetchQueries`) |
| Gesture during `isRefreshing` | ignored (GWT-5) |
| `pointerleave`/`pointercancel` during | treated as a release below threshold — spring back |
| Rotation / viewport change during gesture | reset distance |

## Out of scope

- Mouse drag handling on desktop.
- Per-screen individual thresholds/labels.
- Pull-to-refresh for lists in the middle of the page (e.g. a single card) — we refresh globally.

## Documents to update

- `docs/technical/frontend.md` — section on PTR (hook + wrapper + threshold + touch-only restriction).
- `AGENTS.md` — one sentence in facts (mobile UX).
