# API cold-start lamp — Implementation Plan

> **For agentic workers:** execute inline with TDD. Don't commit until the user asks.

**Goal:** A lamp in the header only when the backend (Render Free) is waking up; after `200` it disappears and **doesn't** keep the server alive with pings.

**Architecture:** Pure state machine in `frontend/src/lib/api-health.ts` (Vitest tests). Hook `useApiHealthProbe` in App interprets states and calls `GET /api/health` only in the wake-up window. `apiFetch` / SSE report a network error or slow request → new window. The lamp reads the store; `/login` doesn't start probing on mount.

**Tech Stack:** Vite, React, Zustand, TanStack Query, Vitest, shadcn Popover.

## Global Constraints

- Waking text: `Waking up the application, please wait.`
- Down text: `Can't connect to the server. We'll try again.`
- Waking ≥ 2 s, down ≥ 90 s, attempt timeout 8 s, break 4 s.
- Forbidden `refetchInterval` on health; background tab and `/login` mount = zero `/api/health`.
- After 200: `queryClient.invalidateQueries`, stop probing.

## Status

- [x] Task 1: State machine (`api-health.ts` + tests)
- [x] Task 2: Store + probe + lamp + wiring (AppShell, apiFetch, SSE, login)
- [x] Tests / lint / build frontend (2026-08-16)
