# Backend

FastAPI app on Render. Root context: `../AGENTS.md`, `../docs/technical/local-setup.md`.

## Commands

From `backend/`:

- Install: `uv sync --all-extras --dev`
- Dev: `uv run uvicorn app.main:app --reload --port 8000`
- Test: `uv run pytest`
- Lint: `uv run ruff check .` and `uv run ruff format --check .`
- Types: `uv run mypy app/domain app/llm`

Liveness: `GET /api/health` → `{ "status": "ok", "service": "goat" }`.
