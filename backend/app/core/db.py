"""Async DB engine (SQLAlchemy Core, nie ORM) + asyncpg — architecture.md sekcja 2.

Migracje idą osobnym torem (Supabase CLI, surowy SQL w `supabase/migrations/`), więc
ORM-owe mapowanie relacji/migracji byłoby dublowaniem systemu — stąd Core, nie ORM.
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

# NullPool: pooling robi Supavisor (Supabase), aplikacja go nie duplikuje drugą
# warstwą poolingu po swojej stronie.
#
# connect_args={"statement_cache_size": 0}: OBOWIĄZKOWE dla kompatybilności z Supavisor
# w trybie transaction. asyncpg domyślnie cache'uje prepared statements po stronie
# klienta, kluczując po tekście zapytania na DANYM fizycznym połączeniu. W trybie
# transaction Supavisor przydziela inne fizyczne połączenie backendu Postgresa do
# każdej transakcji — statement przygotowany na jednym backendzie nie istnieje na
# kolejnym, co kończy się błędem "prepared statement ... does not exist". Wyłączenie
# cache po stronie klienta (statement_cache_size=0) to jedyny bezpieczny sposób
# działania w tym trybie (patrz architecture.md sekcja 2, ADR-3).
engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool,
    connect_args={"statement_cache_size": 0},
)

# service_role — osobny "silnik" logiczny dla /admin/* i Supabase Admin API (architecture.md
# §2, ADR-3). W tym repo `DATABASE_URL` łączy się jako rola Postgresa z uprawnieniem do
# `SET ROLE service_role` (standardowy setup Supabase: rola połączeniowa jest członkiem
# `service_role`, który ma BYPASSRLS) — więc fizycznie reużywamy ten sam silnik/pulę, ale
# NIGDY nie mieszamy tej ścieżki z `rls_connection` (tam nigdy nie ustawiamy service_role).
# ZAŁOŻENIE / WĄTPLIWOŚĆ: jeśli DSN w produkcji wskazuje na rolę bez uprawnienia do przełączenia
# na `service_role` (np. wąsko uprawniony użytkownik aplikacyjny), potrzebny będzie osobny,
# w pełni odseparowany `DATABASE_URL_SERVICE_ROLE` — architecture.md mówi wprost "osobny
# silnik/DSN", ale nie precyzuje connection stringa, więc przyjmujemy najprostszy, zgodny
# z domyślnym Supabase wariant.
@asynccontextmanager
async def service_role_connection() -> AsyncIterator[AsyncConnection]:
    """Połączenie z rolą `service_role` (bypass RLS) — wyłącznie dla `/admin/*` i operacji
    wymagających dostępu do wszystkich userów (security.md §2, ADR-3). Nigdy jako fallback
    domyślnej zależności zwykłych endpointów."""
    async with engine.connect() as conn, conn.begin():
        await conn.execute(text("SET LOCAL ROLE service_role"))
        yield conn


@asynccontextmanager
async def rls_connection(claims: dict[str, Any] | None) -> AsyncIterator[AsyncConnection]:
    """Otwiera połączenie z kontekstem RLS ustawionym z JWT claimów zalogowanego usera.

    `SET LOCAL` (NIGDY `SET` sesyjne!) + `set_config(..., is_local=True)` w OBRĘBIE
    jednej transakcji — ustawienie cofa się automatycznie na COMMIT/ROLLBACK. `SET`
    sesyjne przeciekłoby claimy jednego usera do kolejnego requestu, bo Supavisor w
    trybie transaction przydziela fizyczne połączenia z puli, nie 1:1 per HTTP request.

    `claims=None` -> brak kontekstu RLS, sesja jako `anon`/rola domyślna (np. odczyt
    tabel publicznych typu `persona_templates`/`allowed_metrics`). Dla `service_role`
    (Supabase Admin API, `/admin/*`) używaj OSOBNEGO silnika/DSN — nigdy tej funkcji
    jako fallbacku "dla wygody" (security.md sekcja 2, ADR-3).

    Commit następuje automatycznie przy wyjściu z bloku `async with` (bez wyjątku);
    wyjątek w bloku -> rollback (zachowanie `AsyncConnection.begin()`).
    """
    async with engine.connect() as conn, conn.begin():
        if claims is not None:
            await conn.execute(
                text("SELECT set_config('request.jwt.claims', :claims, true)"),
                {"claims": json.dumps(claims)},
            )
            await conn.execute(text("SET LOCAL ROLE authenticated"))
        yield conn
