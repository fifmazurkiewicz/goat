# Coach — frontend

Vite + React + TypeScript + Tailwind + shadcn/ui (UI component code copied manually to
`src/components/ui/`, following the shadcn philosophy — this is not an npm package).

Full architecture: [`docs/technical/frontend.md`](../docs/technical/frontend.md).

## Status

This is a **skeleton** (routing, layout, stores, Supabase/API clients, placeholder pages).
Business logic (SSE chat streaming, persona form, charts with real data) — subsequent stages.

## Requirements

- Node.js 20+
- Dev project in Supabase Cloud (URL + anon key) — see [`../docs/technical/local-setup.md`](../docs/technical/local-setup.md)
- Backend running locally (by default `http://localhost:8000`) — optional at start, some screens
  (e.g. login) work without it

## Installation and local running

```bash
cd frontend
npm install
cp .env.example .env.local
# fill in VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in .env.local
npm run dev
```

The application will start at `http://localhost:3000`.

## Scripts

| Script | Description |
|---|---|
| `npm run dev` | Development server (Vite, HMR) |
| `npm run build` | Type check (`tsc -b`) + production build |
| `npm run preview` | Preview production build |
| `npm run lint` | ESLint |
| `npm run test` | Unit tests (Vitest + React Testing Library) |

## Environment variables

See [`.env.example`](./.env.example). All variables must have the `VITE_` prefix so Vite
exposes them to client code.

## Structure

```
src/
├── components/
│   ├── ui/        # shadcn/ui — code copied manually (button, card, input, textarea, sheet...)
│   └── layout/    # AppShell (app shell for protected routes)
├── lib/           # supabase.ts, api-client.ts, utils.ts (cn helper)
├── pages/         # pages routed in App.tsx
├── store/         # zustand — client/UI state (see frontend.md #2)
├── types/         # API types (eventually generated from /openapi.json)
└── App.tsx / main.tsx
```
