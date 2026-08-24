"""`UsageLimitsRepo` — `usage_limits` table, USD budget per account (ADR-16).

Same pattern as `PersonasRepo`. Billing period: MONTHLY (`period_start` = first day of
the current UTC month) — documentation (`architecture.md` §9, ADR-16) does not specify
period length explicitly, only the `(user_id, period_start)` key; we use a month as the
most natural granularity for a cost budget (consistent with existing `messages_used`/
`plan_generations_used` counters, which also make sense as monthly metrics).

"Reserve + reconcile" model (see `app/domain/usage/service.py` for full rationale): real
LLM turn cost is known only AFTER the OpenRouter response
(`usage.prompt_tokens`/`completion_tokens` in the final stream chunk), so the atomic
check+increment from architecture.md §9 runs on an ESTIMATED cost BEFORE the call
(gate — blocks spending), and `reconcile` adjusts to the actual cost AFTER
(no second gate — already admitted).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.repositories._row_utils import as_float, stringify_uuid


@dataclass(frozen=True, slots=True)
class UsageLimitsRow:
    user_id: str
    period_start: date
    messages_used: int
    tokens_used: int
    plan_generations_used: int
    cost_usd_used: float


def _row_to_usage(row: Any) -> UsageLimitsRow:
    mapping = dict(row._mapping)
    mapping["user_id"] = stringify_uuid(mapping["user_id"])
    mapping["cost_usd_used"] = as_float(mapping["cost_usd_used"])
    return UsageLimitsRow(**mapping)


class UsageLimitsRepo:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def _ensure_row(self, user_id: str, period_start: date) -> None:
        await self._conn.execute(
            text(
                """
                INSERT INTO usage_limits (user_id, period_start)
                VALUES (:user_id, :period_start)
                ON CONFLICT (user_id, period_start) DO NOTHING
                """
            ),
            {"user_id": user_id, "period_start": period_start},
        )

    async def try_reserve(
        self,
        *,
        user_id: str,
        period_start: date,
        amount_usd: float,
        message_delta: int = 0,
        plan_generation_delta: int = 0,
    ) -> UsageLimitsRow | None:
        """Atomic check+increment (architecture.md §9): `UPDATE ... WHERE cost_usd_used
        + :amount <= (SELECT usage_budget_usd FROM profiles ...) RETURNING ...` in a SINGLE
        query — race-condition-safe. `None` = rejected (budget exceeded)."""
        await self._ensure_row(user_id, period_start)
        result = await self._conn.execute(
            text(
                """
                UPDATE usage_limits
                SET cost_usd_used = cost_usd_used + :amount,
                    messages_used = messages_used + :message_delta,
                    plan_generations_used = plan_generations_used + :plan_generation_delta
                WHERE user_id = :user_id AND period_start = :period_start
                  AND cost_usd_used + :amount <= (
                    SELECT usage_budget_usd FROM profiles WHERE id = :user_id
                  )
                RETURNING user_id, period_start, messages_used, tokens_used,
                          plan_generations_used, cost_usd_used
                """
            ),
            {
                "user_id": user_id,
                "period_start": period_start,
                "amount": amount_usd,
                "message_delta": message_delta,
                "plan_generation_delta": plan_generation_delta,
            },
        )
        row = result.one_or_none()
        return _row_to_usage(row) if row is not None else None

    async def reconcile(
        self, *, user_id: str, period_start: date, delta_usd: float, tokens_delta: int = 0
    ) -> None:
        """Adjust to actual cost after the LLM response (see module docstring) —
        `GREATEST(..., 0)` prevents negative `cost_usd_used` if actual cost were below
        the reservation (should not happen, but a cheap assertion)."""
        await self._ensure_row(user_id, period_start)
        await self._conn.execute(
            text(
                """
                UPDATE usage_limits
                SET cost_usd_used = GREATEST(cost_usd_used + :delta, 0),
                    tokens_used = tokens_used + :tokens_delta
                WHERE user_id = :user_id AND period_start = :period_start
                """
            ),
            {
                "user_id": user_id,
                "period_start": period_start,
                "delta": delta_usd,
                "tokens_delta": tokens_delta,
            },
        )

    async def get(self, user_id: str, period_start: date) -> UsageLimitsRow | None:
        result = await self._conn.execute(
            text(
                """
                SELECT user_id, period_start, messages_used, tokens_used,
                       plan_generations_used, cost_usd_used
                FROM usage_limits
                WHERE user_id = :user_id AND period_start = :period_start
                """
            ),
            {"user_id": user_id, "period_start": period_start},
        )
        row = result.one_or_none()
        return _row_to_usage(row) if row is not None else None

    async def list_for_period(self, period_start: date) -> dict[str, UsageLimitsRow]:
        """All users in the given period — for `/admin/users` (requires `service_role`;
        RLS would limit a regular user to their own row)."""
        result = await self._conn.execute(
            text(
                """
                SELECT user_id, period_start, messages_used, tokens_used,
                       plan_generations_used, cost_usd_used
                FROM usage_limits
                WHERE period_start = :period_start
                """
            ),
            {"period_start": period_start},
        )
        rows = [_row_to_usage(row) for row in result]
        return {row.user_id: row for row in rows}
