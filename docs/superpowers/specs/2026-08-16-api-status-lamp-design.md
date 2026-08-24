# Design: API status lamp (Render cold start)

**Date:** 2026-08-16  
**Status:** implemented (2026-08-16)  
**Related:** ADR-19 · [`docs/technical/frontend.md`](../../technical/frontend.md) · [`docs/technical/devops.md`](../../technical/devops.md)

## Problem

The frontend on Vercel starts immediately. The backend on Render Free sleeps after ~15 min of inactivity; the first requests to the API can hang for 30–60 s. The user sees empty lists / "Failed to fetch" and refreshes the page, not knowing the server is waking up.

## Goal

A small **lamp only when we're waiting for the API**. Hover (desktop) or tap (phone) explains what's happening. After waking up the lamp **disappears**. TanStack Query requests retry themselves — without F5.

**The backend must be allowed to sleep.** The lamp is not a heartbeat. No cyclic `/api/health` when the app is already running or the tab is in the background.

## States

| UI state | When | Lamp | Text (hover / tap) |
|----------|------|------|--------------------|
| `hidden` | API responding **or** nothing is waiting now | none | — |
| `waking` | real request (or wake-up probe) hanging ≥ 2 s | amber, pulsing | Waking up the app, please wait. |
| `down` | still no success after ~90 s | red, no pulse | We can't connect to the server. We'll try again. |

By default nothing is visible (locally and when Render is already warm). There is no green "all OK" lamp.

## Probing — hard rules

You may send `GET {VITE_API_BASE_URL}/api/health` (public, no JWT; contract unchanged: `200` + `{"status":"ok"}`) **only** in the wake-up window:

1. **Window start:** AppShell mount (or network error in `apiFetch` / SSE, not 4xx/5xx with JSON). Just mounting `/login` **doesn't** ping — Google OAuth doesn't need Render; pinging every login opening would wake the server needlessly.
2. **In window:** probe timeout 8 s; next probe every 4 s, **only** when the tab is visible (`document.visibilityState === "visible"`).
3. **Window end (immediate stop, zero further health):** first 200 **or** ~90 s without 200 **or** tab goes to background. After `down` the auto-stop **does not** spin further; tap on lamp = one new window (again max ~90 s).
4. **After 200:** lamp disappears, `queryClient.invalidateQueries()` (outside health). As long as the next **real** user requests pass, **no** `/api/health`.

Forbidden: `refetchInterval` when healthy; ping every N seconds "just in case"; keep-alive in the background; ping when tab is hidden.

## UI

- Location: AppShell header next to "Coach". On `/login` the lamp only if that page actually waits for the API (dev-login), not on entry alone.
- Hit area ≥ 44px; dot ~10px.
- Hover opens a short text; tap/click too. No banner, no overlay.
- `aria-label` = content from the table; when lamp visible: `role="status"` / `aria-live="polite"`.

## Out of scope

- Overlay / banner / toast on every error.
- External keep-alive (UptimeRobot, cron) and any ping that keeps Render artificially alive.
- Changing `/api/health` (stays liveness without DB).
- Render Free → Starter upgrade.

## Requirements (Given / When / Then)

### GWT-1 — warm backend: silence

**Given** the first health (or a regular AppShell request) returns 200 in less than 2 s  
**When** the user is in the app  
**Then** the lamp is not rendered  
**And** there are no further `/api/health` calls

### GWT-2 — cold start: lamp and text

**Given** AppShell is waiting for the API and no 200 for at least 2 s  
**When** the user looks at the header  
**Then** an amber pulsing lamp is visible  
**And** hover or tap shows "Waking up the app, please wait."

### GWT-3 — after waking up it disappears, data returns, pings stop

**Given** lamp in `waking` state  
**When** health returns 200  
**Then** the lamp disappears  
**And** TanStack Query queries that failed on timeout/network are retried without refreshing the page  
**And** frontend **does not** send more `/api/health` until a new window opens from GWT-6

### GWT-4 — long-lasting failure: stop the autoloop

**Given** wake-up window lasting ~90 s without 200  
**When** the user taps the lamp  
**Then** color is red (no pulse)  
**And** text: "We can't connect to the server. We'll try again."  
**And** automatic `/api/health` no longer go out  
**And** tap starts **one** new wake-up window (again ~90 s limit)

### GWT-5 — login does not wake Render on its own

**Given** the user is on `/login` and nothing sends to the API  
**When** the page mounts  
**Then** no `/api/health` request  
**And** the lamp is not visible

### GWT-6 — re-sleep only on a real error

**Given** API was OK, lamp hidden, no probe  
**When** `apiFetch` / SSE ends with a network error (not 4xx/5xx with JSON)  
**Then** a new wake-up window starts; after 2 s without 200 the lamp returns to `waking`

### GWT-7 — background tab does not keep the server alive

**Given** a wake-up window is in progress or the app is already "healthy"  
**When** tab is in background (`visibilityState !== "visible"`) or the user doesn't do anything for 15 min  
**Then** frontend does not send `/api/health`  
**And** Render Free can sleep
