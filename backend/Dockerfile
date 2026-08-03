# Zgodnie z docs/technical/devops.md sekcja 1: python:3.12-slim, ca-certificates
# (wymagane do SSL po połączeniu z Supabase), uvicorn bindujący 0.0.0.0:$PORT.
# Render: Root Directory = backend/, Health Check = /api/health.
FROM python:3.12-slim

# ca-certificates — bez tego SSL handshake do Supabase (asyncpg/httpx) się wywala.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Oficjalny statyczny binarny uv, bez dodatkowej warstwy pip install.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Warstwa zależności osobno od kodu — cache Dockera nie inwaliduje się przy zmianie appki.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 10000

# Shell form (nie exec/JSON form) — konieczne, żeby zmienna $PORT (ustawiana przez
# Render w runtime) faktycznie się rozwinęła przed startem procesu.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}
