# Per docs/technical/devops.md section 1: python:3.12-slim, ca-certificates
# (required for SSL when connecting to Supabase), uvicorn binding 0.0.0.0:$PORT.
# Render: Root Directory = backend/, Health Check = /api/health.
FROM python:3.14-slim

# ca-certificates — without this, SSL handshake to Supabase (asyncpg/httpx) fails.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Official static uv binary, no extra pip install layer.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Dependency layer separate from code — Docker cache is not invalidated by app changes.
COPY pyproject.toml uv.lock VERSION ./
RUN uv sync --frozen --no-dev

COPY app ./app

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 10000

# Shell form (not exec/JSON form) — required so the $PORT variable (set by
# Render at runtime) actually expands before the process starts.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}