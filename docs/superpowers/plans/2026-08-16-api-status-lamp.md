# Lampka cold startu API — Implementation Plan

> **For agentic workers:** execute inline with TDD. Nie commituj, dopóki user nie poprosi.

**Goal:** Lampka w headerze tylko gdy backend (Render Free) się budzi; po `200` znika i **nie** trzyma serwera przy życiu pingami.

**Architecture:** Czysta maszyna stanów w `frontend/src/lib/api-health.ts` (testy Vitest). Hook `useApiHealthProbe` w App interpretuje stany i woła `GET /api/health` wyłącznie w oknie wybudzania. `apiFetch` / SSE zgłaszają błąd sieci lub wolny request → nowe okno. Lampka czyta store; `/login` nie startuje sondy na mount.

**Tech Stack:** Vite, React, Zustand, TanStack Query, Vitest, shadcn Popover.

## Global Constraints

- Tekst waking: `Budzimy aplikację, poczekaj chwilę.`
- Tekst down: `Nie możemy połączyć się z serwerem. Spróbujemy ponownie.`
- Waking ≥ 2 s, down ≥ 90 s, timeout próby 8 s, przerwa 4 s.
- Zakaz `refetchInterval` na health; karta w tle i `/login` mount = zero `/api/health`.
- Po 200: `queryClient.invalidateQueries`, stop sondy.

## Status

- [x] Task 1: Maszyna stanów (`api-health.ts` + testy)
- [x] Task 2: Store + sonda + lampka + wiring (AppShell, apiFetch, SSE, login)
- [x] Testy / lint / build frontend (2026-08-16)
