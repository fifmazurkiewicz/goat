"""Tests for `UsageLimitService` — atomic check+increment of USD budget (ADR-16,
architecture.md §9)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from app.core.exceptions import UsageLimitExceededError
from app.domain.usage.service import UsageLimitService, current_period_start


@dataclass
class _FakeUsageRow:
    user_id: str
    period_start: date
    cost_usd_used: float
    messages_used: int = 0
    tokens_used: int = 0
    plan_generations_used: int = 0


@dataclass
class _FakeProfile:
    usage_budget_usd: float


class _FakeUsageRepo:
    """Simulates the database budget gate: `try_reserve` rejects (`None`) when it would
    exceed the budget, otherwise atomically increments `cost_usd_used`."""

    def __init__(self, budget: float, already_used: float = 0.0) -> None:
        self._budget = budget
        self.row = _FakeUsageRow(user_id="u1", period_start=current_period_start(), cost_usd_used=already_used)

    async def try_reserve(
        self,
        *,
        user_id: str,
        period_start: date,
        amount_usd: float,
        message_delta: int = 0,
        plan_generation_delta: int = 0,
    ) -> _FakeUsageRow | None:
        if self.row.cost_usd_used + amount_usd > self._budget:
            return None
        self.row.cost_usd_used += amount_usd
        self.row.messages_used += message_delta
        self.row.plan_generations_used += plan_generation_delta
        return self.row

    async def reconcile(self, *, user_id: str, period_start: date, delta_usd: float, tokens_delta: int = 0) -> None:
        self.row.cost_usd_used = max(0.0, self.row.cost_usd_used + delta_usd)
        self.row.tokens_used += tokens_delta

    async def get(self, user_id: str, period_start: date) -> _FakeUsageRow | None:
        return self.row


class _FakeProfilesRepo:
    def __init__(self, budget: float) -> None:
        self._profile = _FakeProfile(usage_budget_usd=budget)

    async def get(self, user_id: str) -> _FakeProfile | None:
        return self._profile


class _FakePricingCache:
    def __init__(self, usd_per_token: float = 0.00001) -> None:
        self._usd_per_token = usd_per_token

    async def estimate_cost_usd(self, *, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        return (prompt_tokens + completion_tokens) * self._usd_per_token


async def test_reserve_estimated_cost_allowed_below_budget() -> None:
    usage_repo = _FakeUsageRepo(budget=10.0)
    service = UsageLimitService(usage_repo, _FakeProfilesRepo(10.0), _FakePricingCache())

    period_start = await service.reserve_estimated_cost(user_id="u1", estimated_cost_usd=1.0)

    assert period_start == current_period_start()
    assert usage_repo.row.cost_usd_used == 1.0
    assert usage_repo.row.messages_used == 1


async def test_reserve_estimated_cost_raises_when_over_budget() -> None:
    usage_repo = _FakeUsageRepo(budget=1.0, already_used=0.9)
    service = UsageLimitService(usage_repo, _FakeProfilesRepo(1.0), _FakePricingCache())

    with pytest.raises(UsageLimitExceededError):
        await service.reserve_estimated_cost(user_id="u1", estimated_cost_usd=0.5)

    # Rejected reservation does NOT modify state (atomicity — no partial write).
    assert usage_repo.row.cost_usd_used == 0.9


async def test_reconcile_actual_cost_corrects_estimate_downward() -> None:
    usage_repo = _FakeUsageRepo(budget=10.0)
    service = UsageLimitService(usage_repo, _FakeProfilesRepo(10.0), _FakePricingCache())

    period_start = await service.reserve_estimated_cost(user_id="u1", estimated_cost_usd=2.0)
    await service.reconcile_actual_cost(
        user_id="u1", period_start=period_start, estimated_cost_usd=2.0, actual_cost_usd=0.5
    )

    assert usage_repo.row.cost_usd_used == pytest.approx(0.5)


async def test_reserve_plan_generation_increments_plan_counter_not_messages() -> None:
    usage_repo = _FakeUsageRepo(budget=10.0)
    service = UsageLimitService(usage_repo, _FakeProfilesRepo(10.0), _FakePricingCache())

    await service.reserve_plan_generation(user_id="u1", estimated_cost_usd=1.0)

    assert usage_repo.row.plan_generations_used == 1
    assert usage_repo.row.messages_used == 0


async def test_estimate_turn_cost_uses_pricing_cache() -> None:
    service = UsageLimitService(_FakeUsageRepo(10.0), _FakeProfilesRepo(10.0), _FakePricingCache(usd_per_token=0.0001))

    cost = await service.estimate_turn_cost_usd(model="test-model", prompt_text_length_chars=400, max_output_tokens=100)

    # 400 chars / 4 chars-per-token = 100 input tokens + 100 output tokens = 200 * 0.0001
    assert cost == pytest.approx(0.02)
