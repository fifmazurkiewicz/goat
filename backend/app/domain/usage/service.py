"""`UsageLimitService` — budżet USD per konto, atomowy check+increment (ADR-16).

Pełny opis: docs/technical/architecture.md sekcja 9, docs/technical/ai-pipeline.md
sekcja 1b, docs/technical/security.md sekcja 4. Generowanie planu debituje z TEGO
SAMEGO limitera co czat (jedna pula per user, per okres rozliczeniowy).

**Model "rezerwacja + rekoncyliacja"** (decyzja implementacyjna, dokumentacja nie
precyzuje mechaniki poniżej tego poziomu szczegółu): koszt realnej tury LLM jest znany
dopiero PO odpowiedzi OpenRoutera (`usage.prompt_tokens`/`completion_tokens` w finalnym
chunku streamu) — nie da się więc zrobić czystego "check PRZED, increment PO" na tym
samym, dokładnym koszcie. Zamiast tego:

1. `reserve_estimated_cost` — PRZED wywołaniem LLM, atomowy check+increment na
   SZACOWANYM koszcie (długość promptu * cena/token + `max_tokens` konfiguracji *
   cena/token output, konserwatywnie w górę) — to jest realna bramka budżetowa,
   blokuje wydanie pieniędzy `UsageLimitExceededError` (429) PRZED requestem.
2. `reconcile_actual_cost` — PO odpowiedzi, koryguje `cost_usd_used` na rzeczywisty
   koszt (różnica estymacja-rzeczywistość, może być ujemna) — BEZ ponownej bramki
   (transakcja już przepuszczona), tylko księgowa poprawka dla dokładności panelu admina.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from app.core.exceptions import UsageLimitExceededError
from app.domain.usage.pricing import ModelPricingCache


def current_period_start(today: date | None = None) -> date:
    """Pierwszy dzień bieżącego miesiąca UTC — granulacja okresu rozliczeniowego
    (patrz `app/repositories/usage_limits_repo.py` dla uzasadnienia wyboru miesiąca)."""
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

    async def reconcile(
        self, *, user_id: str, period_start: date, delta_usd: float, tokens_delta: int = 0
    ) -> None: ...

    async def get(self, user_id: str, period_start: date) -> object | None: ...


class ProfilesRepositoryProtocol(Protocol):
    async def get(self, user_id: str) -> object | None: ...


# Grube oszacowanie znaków/token dla estymacji kosztu PRZED wywołaniem (wystarczające
# dla bramki budżetowej — dokładny koszt liczy się i tak dopiero z realnego `usage`).
_CHARS_PER_TOKEN_ESTIMATE = 4


class UsageLimitService:
    """Nie zna FastAPI/HTTP — testowalna z fake repo (architecture.md sekcja 7)."""

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
        """Konserwatywne oszacowanie kosztu tury PRZED wywołaniem LLM."""
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

    async def reserve_estimated_cost(
        self, *, user_id: str, estimated_cost_usd: float, is_message: bool = True
    ) -> date:
        """Bramka budżetowa PRZED wywołaniem LLM — zwraca `period_start` użyty (do
        późniejszej rekoncyliacji), rzuca `UsageLimitExceededError` (429) gdy odrzucone."""
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
        """Korekta po odpowiedzi LLM — bez ponownej bramki (patrz docstring modułu)."""
        delta = actual_cost_usd - estimated_cost_usd
        await self._usage_repo.reconcile(
            user_id=user_id, period_start=period_start, delta_usd=delta, tokens_delta=actual_tokens
        )

    async def reserve_plan_generation(self, *, user_id: str, estimated_cost_usd: float) -> date:
        """Jak `reserve_estimated_cost`, ale inkrementuje `plan_generations_used` zamiast
        `messages_used` — ten sam wiersz `usage_limits`/budżet (jedna pula per user)."""
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
