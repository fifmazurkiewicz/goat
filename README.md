# Goat — Multi-Persona Coaching App

A web app where the user configures up to 5 trainer personas (dietitian, gym coach, badminton coach, sports psychologist, psychologist, motor-skills coach), chats with them with memory, and agents save results (gym, diet, pool, triathlon, badminton) to the database. Personas collaborate on generating a shared, synchronized week/month plan visible in the calendar.

## Stack

- **Frontend:** Vite + React + TypeScript + Tailwind + shadcn/ui → Vercel
- **Backend:** Python (FastAPI) → Render
- **DB + Auth:** Supabase (Postgres, RLS, Auth: Google OAuth)
- **LLM:** OpenRouter (structured output via native `response_format: json_schema`)
- **DNS:** Cloudflare

## Documentation

Full technical specification, architectural decisions and implementation plan — in [`docs/`](docs/):

- [`docs/technical/architecture.md`](docs/technical/architecture.md) — backend architecture, chat flow (SSE + tool calling), plan generation pipeline
- [`docs/technical/database-schema.md`](docs/technical/database-schema.md) — full database schema + RLS
- [`docs/technical/security.md`](docs/technical/security.md) — security, jailbreak defense, RLS vs service role
- [`docs/technical/ai-pipeline.md`](docs/technical/ai-pipeline.md) — AI layer: models, moderation, plan generation, quality tests
- [`docs/technical/frontend.md`](docs/technical/frontend.md) — frontend architecture, routing, state management, SSE client
- [`docs/technical/devops.md`](docs/technical/devops.md) — deploy, CI/CD, migrations, secrets, costs
- [`docs/technical/cloud-setup.md`](docs/technical/cloud-setup.md) — cloud setup (Supabase / Render / Vercel / Cloudflare) — **current path**
- [`docs/technical/local-setup.md`](docs/technical/local-setup.md) — local loop + Graft (§G, ADR-20)
- [`docs/technical/configuration.md`](docs/technical/configuration.md) — env variable **names** (no secrets)
- [`docs/adr/decisions.md`](docs/adr/decisions.md) — log of key architectural decisions (ADR)

## Status

Implementation in progress. Backend/frontend skeleton (routing, layers, DI) is ready; business logic
for individual domains (personas, chat, plans, results, admin, exercise catalog, account settings)
is being filled in per `docs/adr/decisions.md`.
