# Backend

FastAPI app on Render. Root context: `../AGENTS.md`, `../docs/technical/local-setup.md`.

`app/` is the backend package root. Keep FastAPI routes and Supabase/OpenRouter
clients at the edge; application orchestration and coaching rules must not
depend on FastAPI or provider SDKs. Wire concrete integrations in the
application entrypoint without migrating unrelated frontend or SQL migration
code.

## Commands

From `backend/`:

- Install: `uv sync --all-extras --dev`
- Dev: `uv run uvicorn app.main:app --reload --port 8000`
- Test: `uv run pytest`
- Lint: `uv run ruff check .` and `uv run ruff format --check .`
- Types: `uv run mypy app/domain app/llm`

Liveness: `GET /api/health` → `{ "status": "ok", "service": "goat" }`.
