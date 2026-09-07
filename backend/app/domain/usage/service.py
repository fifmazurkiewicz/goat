"""`UsageLimitService` — USD budget per account, atomic check+increment (ADR-16).

Full description: docs/technical/architecture.md section 9, docs/technical/ai-pipeline.md
section 1b, docs/technical/security.md section 4. Plan generation debits the SAME
limiter as chat (one pool per user, per billing period).

**"Reservation + reconciliation" model** (implementation decision, documentation does
not go deeper than this level of detail): the real cost of an LLM turn is only known
AFTER the OpenRouter response (`usage.prompt_tokens`/`completion_tokens` in the final
stream chunk) — you can't make a clean "check BEFORE, increment AFTER" on the same
exact cost. Instead:

1. `reserve_estimated_cost` — BEFORE the LLM call, atomic check+increment on the
   ESTIMATED cost (prompt length * price/token + configured `max_tokens` *
   output price/token, conservatively upward) — this is the real budget gate,
   blocks spending with `UsageLimitExceededError` (429) BEFORE the request.
2. `reconcile_actual_cost` — AFTER the response, corrects `cost_usd_used` to the
   actual cost (estimate-reality difference, can be negative) — WITHOUT a second
   gate (transaction already passed through), only an accounting fix for admin
   panel accuracy.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from app.core.exceptions import UsageLimitExceededError
from app.domain.usage.pricing import ModelPricingCache


def current_period_start(today: date | None = None) -> date:
    """First day of the current UTC month — billing period granularity
    (see `app/repositories/usage_limits_repo.py` for the rationale of choosing a month)."""
    day = today or date.today()
    return day.replace(day=1)


class UsageLimitsRepositoryProtocol(Protocol):
    async def try_reserve(
        self,
        *,
        user_id: str,
        period_start: date,
        amount_usd: float,
        message_delta: int = 0,
        plan_generation_delta: int = 0,
    ) -> object | None: ...

    async def reconcile(self, *, user_id: str, period_start: date, delta_usd: float, tokens_delta: int = 0) -> None: ...

    async def get(self, user_id: str, period_start: date) -> object | None: ...


class ProfilesRepositoryProtocol(Protocol):
    async def get(self, user_id: str) -> object | None: ...


# Rough chars/token estimate for cost estimation BEFORE the call (good enough for the
# budget gate — the exact cost is only computed from the real `usage` anyway).
_CHARS_PER_TOKEN_ESTIMATE = 4


class UsageLimitService:
    """Doesn't know FastAPI/HTTP — testable with a fake repo (architecture.md section 7)."""

    def __init__(
        self,
        usage_repo: UsageLimitsRepositoryProtocol,
        profiles_repo: ProfilesRepositoryProtocol,
        pricing_cache: ModelPricingCache,
    ) -> None:
        self._usage_repo = usage_repo
        self._profiles_repo = profiles_repo
        self._pricing_cache = pricing_cache

    async def estimate_turn_cost_usd(
        self, *, model: str, prompt_text_length_chars: int, max_output_tokens: int
    ) -> float:
        """Conservative turn cost estimate BEFORE the LLM call."""
        estimated_prompt_tokens = max(1, prompt_text_length_chars // _CHARS_PER_TOKEN_ESTIMATE)
        return await self._pricing_cache.estimate_cost_usd(
            model=model,
            prompt_tokens=estimated_prompt_tokens,
            completion_tokens=max_output_tokens,
        )

    async def _raise_limit_exceeded(self, user_id: str, period_start: date) -> None:
        usage = await self._usage_repo.get(user_id, period_start)
        profile = await self._profiles_repo.get(user_id)
        budget = getattr(profile, "usage_budget_usd", None)
        used = getattr(usage, "cost_usd_used", 0.0) if usage else 0.0
        next_period = date(
            period_start.year + (1 if period_start.month == 12 else 0),
            1 if period_start.month == 12 else period_start.month + 1,
            1,
        )
        budget_txt = f"${budget:.2f}" if budget is not None else "nieznanym limicie"
        raise UsageLimitExceededError(
            f"Przekroczono budżet konta: wykorzystano ${used:.2f} z {budget_txt}. "
            f"Odnowienie budżetu {next_period.isoformat()}. Poproś administratora "
            "o zwiększenie budżetu, jeśli to konieczne."
        )

    async def reserve_estimated_cost(self, *, user_id: str, estimated_cost_usd: float, is_message: bool = True) -> date:
        """Budget gate BEFORE the LLM call — returns the `period_start` used (for later
        reconciliation), raises `UsageLimitExceededError` (429) when rejected."""
        period_start = current_period_start()
        row = await self._usage_repo.try_reserve(
            user_id=user_id,
            period_start=period_start,
            amount_usd=estimated_cost_usd,
            message_delta=1 if is_message else 0,
        )
        if row is None:
            await self._raise_limit_exceeded(user_id, period_start)
        return period_start

    async def reconcile_actual_cost(
        self,
        *,
        user_id: str,
        period_start: date,
        estimated_cost_usd: float,
        actual_cost_usd: float,
        actual_tokens: int = 0,
    ) -> None:
        """Correction after the LLM response — without a second gate (see module docstring)."""
        delta = actual_cost_usd - estimated_cost_usd
        await self._usage_repo.reconcile(
            user_id=user_id, period_start=period_start, delta_usd=delta, tokens_delta=actual_tokens
        )

    async def reserve_plan_generation(self, *, user_id: str, estimated_cost_usd: float) -> date:
        """Like `reserve_estimated_cost`, but increments `plan_generations_used` instead of
        `messages_used` — same `usage_limits` row/budget (one pool per user)."""
        period_start = current_period_start()
        row = await self._usage_repo.try_reserve(
            user_id=user_id,
            period_start=period_start,
            amount_usd=estimated_cost_usd,
            plan_generation_delta=1,
        )
        if row is None:
            await self._raise_limit_exceeded(user_id, period_start)
        return period_start
