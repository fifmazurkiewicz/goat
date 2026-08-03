# Backend — Multi-Persona Coaching App

FastAPI (Python 3.12+), zarządzany przez [`uv`](https://docs.astral.sh/uv/). Pełna
architektura opisana w [`../docs/technical/architecture.md`](../docs/technical/architecture.md);
schemat bazy w [`../docs/technical/database-schema.md`](../docs/technical/database-schema.md).

## Status

Szkielet fundamentu — routing, konfiguracja, autentykacja JWT, dostęp do bazy z RLS,
logging, globalny error handling. **Bez logiki biznesowej** (chat orchestrator, plan
generation, moderacja) — to osobne, kolejne etapy. Miejsca oznaczone `TODO` /
`NotImplementedError` w `app/domain/`, `app/llm/` i `app/core/security.py::require_admin`
wskazują dokładnie co zostało odłożone i do jakiej sekcji dokumentacji się odnosi.

## Instalacja

```bash
cd backend
uv sync
```

## Konfiguracja

```bash
cp .env.example .env
```

Uzupełnij w `.env` realne wartości: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWKS_URL`,
`SUPABASE_SERVICE_ROLE_KEY`, `OPENROUTER_API_KEY`. Nigdy nie commituj `.env` (już objęty
głównym `.gitignore`). Rekomendowany setup lokalny: dev project Supabase Cloud — patrz
[`../docs/technical/local-setup.md`](../docs/technical/local-setup.md).

## Uruchomienie

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Smoke test: `curl http://localhost:8000/api/health` → `{"status":"ok"}`.

## Testy

```bash
uv run pytest
```

Testy wymagają obecności `.env` (ładowanego przez `pydantic-settings`) — wystarczą
placeholdery z `.env.example`, endpoint health nie dotyka bazy ani zewnętrznych usług.

## Lint / typy

```bash
uv run ruff check .
uv run ruff format .
uv run mypy app
```
