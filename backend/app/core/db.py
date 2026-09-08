"""Async DB engine (SQLAlchemy Core, not ORM) + asyncpg — architecture.md section 2.

Migrations go a separate route (Supabase CLI, raw SQL in `supabase/migrations/`), so
ORM-style relation/migration mapping would duplicate the system — hence Core, not ORM.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings


def _asyncpg_url(url: str) -> str:
    """Forces the `postgresql+asyncpg` dialect — plain `postgresql://` maps to the
    synchronous psycopg2, which we don't have as a dependency (architecture.md §2)."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    return url


# NullPool: pooling is done by Supavisor (Supabase), the app does not duplicate a
# second pooling layer of its own.
#
# connect_args={"statement_cache_size": 0}: REQUIRED for compatibility with Supavisor
# in transaction mode. asyncpg by default caches prepared statements on the client
# side, keyed by query text on a GIVEN physical connection. In transaction mode,
# Supavisor assigns a different physical Postgres backend connection to each
# transaction — a statement prepared on one backend doesn't exist on the next,
# which ends in a "prepared statement ... does not exist" error. Disabling the
# client-side cache (statement_cache_size=0) is the only safe way to work in this
# mode (see architecture.md section 2, ADR-3).
engine = create_async_engine(
    _asyncpg_url(settings.database_url),
    poolclass=NullPool,
    connect_args={"statement_cache_size": 0},
)


# service_role — a separate logical "engine" for /admin/* and Supabase Admin API
# (architecture.md §2, ADR-3). In this repo `DATABASE_URL` connects as a Postgres role
# with permission to `SET ROLE service_role` (standard Supabase setup: the connection
# role is a member of `service_role`, which has BYPASSRLS) — so we physically reuse
# the same engine/pool, but NEVER mix this path with `rls_connection` (where we never
# set service_role).
# ASSUMPTION / DOUBT: if the production DSN points to a role without permission to
# switch to `service_role` (e.g. a narrowly-privileged app user), a separate, fully
# isolated `DATABASE_URL_SERVICE_ROLE` will be needed — architecture.md says plainly
# "separate engine/DSN", but doesn't specify the connection string, so we assume the
# simplest, Supabase-default variant.
@asynccontextmanager
async def service_role_connection() -> AsyncIterator[AsyncConnection]:
    """Connection as the `service_role` role (bypass RLS) — ONLY for `/admin/*` and
    operations requiring access across all users (security.md §2, ADR-3). Never as a
    fallback for the default dependency of regular endpoints."""
    async with engine.connect() as conn, conn.begin():
        await conn.execute(text("SET LOCAL ROLE service_role"))
        yield conn


@asynccontextmanager
async def login_role_connection() -> AsyncIterator[AsyncConnection]:
    """DATABASE_URL login role (typically `postgres`) — can `SELECT auth.users`.

    Hosted Supabase does not grant `auth.users` to `service_role`. After
    `SET LOCAL ROLE service_role`, that query fail-opens to `{}` and the admin
    Users column renders "—". Do not SET ROLE here.
    """
    async with engine.connect() as conn, conn.begin():
        yield conn


@asynccontextmanager
async def rls_connection(claims: dict[str, Any] | None) -> AsyncIterator[AsyncConnection]:
    """Opens a connection with the RLS context set from the logged-in user's JWT claims.

    `SET LOCAL` (NEVER session-level `SET`!) + `set_config(..., is_local=True)` WITHIN
    a single transaction — the setting is automatically reverted on COMMIT/ROLLBACK.
    Session-level `SET` would leak one user's claims to the next request, because
    Supavisor in transaction mode assigns physical connections from a pool, not 1:1
    per HTTP request.

    `claims=None` -> no RLS context, session as `anon`/default role (e.g. reading
    public tables like `persona_templates`/`allowed_metrics`). For `service_role`
    (Supabase Admin API, `/admin/*`) use a SEPARATE engine/DSN — never this function
    as a "convenience" fallback (security.md section 2, ADR-3).

    Commit happens automatically when exiting the `async with` block (without an
    exception); exception in the block -> rollback (`AsyncConnection.begin()` behavior).
    """
    async with engine.connect() as conn, conn.begin():
        if claims is not None:
            await conn.execute(
                text("SELECT set_config('request.jwt.claims', :claims, true)"),
                {"claims": json.dumps(claims)},
            )
            await conn.execute(text("SET LOCAL ROLE authenticated"))
        yield conn
