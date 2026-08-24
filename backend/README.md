# Backend — Multi-Persona Coaching App

FastAPI (Python 3.12+), managed by [`uv`](https://docs.astral.sh/uv/). Full architecture
described in [`../docs/technical/architecture.md`](../docs/technical/architecture.md);
database schema in [`../docs/technical/database-schema.md`](../docs/technical/database-schema.md).

## Status

Foundation skeleton — routing, configuration, JWT auth, database access with RLS,
logging, global error handling. **Without business logic** (chat orchestrator, plan
generation, moderation) — those are separate, subsequent stages. Places marked `TODO` /
`NotImplementedError` in `app/domain/`, `app/llm/` and `app/core/security.py::require_admin`
indicate exactly what was deferred and which documentation section it relates to.

## Installation

```bash
cd backend
uv sync
```

## Configuration

```bash
cp .env.example .env
```

Fill in real values in `.env`: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWKS_URL`,
`SUPABASE_SERVICE_ROLE_KEY`, `OPENROUTER_API_KEY`. Never commit `.env` (already covered by
the root `.gitignore`). Recommended local setup: Supabase Cloud dev project — see
[`../docs/technical/local-setup.md`](../docs/technical/local-setup.md).

## Running

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Smoke test: `curl http://localhost:8000/api/health` → `{"status":"ok"}`.

## Tests

```bash
uv run pytest
```

Tests require the presence of `.env` (loaded by `pydantic-settings`) — placeholders from
`.env.example` are enough, the health endpoint does not touch the database or external services.

## Lint / types

```bash
uv run ruff check .
uv run ruff format .
uv run mypy app
```
