"""`PlanOrchestrator` — pipeline 3-etapowy generowania planu.

Pełna implementacja: docs/technical/architecture.md sekcja 4 ("Generowanie planu —
pipeline") i docs/technical/ai-pipeline.md sekcja 4. Priorytet produktowy: synchronizacja
planu między aktywnymi personami (ADR-2), nie tylko jakość pojedynczej persony w izolacji.

Uruchamiane z `BackgroundTasks` FastAPI (bez osobnego Render Workera — ADR-1), w tym
samym procesie co web.
"""

from __future__ import annotations

from typing import Any, Protocol


class PlannerLLMClientProtocol(Protocol):
    async def generate(self, *args: Any, **kwargs: Any) -> Any: ...


class PlansRepositoryProtocol(Protocol):
    async def save_plan_items(self, *args: Any, **kwargs: Any) -> Any: ...
    async def update_job_status(self, *args: Any, **kwargs: Any) -> Any: ...


class PlanOrchestrator:
    """Zależności jako `Protocol` — testowalna bez FastAPI/bazy (architecture.md sekcja 7)."""

    def __init__(
        self, llm_client: PlannerLLMClientProtocol, plans_repo: PlansRepositoryProtocol
    ) -> None:
        self._llm_client = llm_client
        self._plans_repo = plans_repo

    async def generate_plan(self, *, plan_id: str, job_id: str) -> None:
        """Uruchamia pełny pipeline 3-etapowy dla danego planu, aktualizując
        `plan_generation_jobs`/`plan_generation_job_personas` w trakcie (partial
        success — patrz architecture.md sekcja 4, model stanu jobów).

        TODO pełna implementacja — patrz docs/technical/architecture.md sekcja 4:

        Etap 1 — COORDINATOR PASS (tani model): wspólny szkielet (rozkład dni
        treningowych/odpoczynku, orientacyjne cele) dla wszystkich aktywnych person.

        Etap 2 — PER-PERSONA GENERACJA (PLANNER_MODEL, RÓWNOLEGLE):
        `asyncio.gather(*persona_tasks, return_exceptions=True)` — NIE `TaskGroup`
        (anuluje wszystko przy pierwszym wyjątku, odwrotność pożądanego zachowania
        dla partial success). Każda persona: własny `system_prompt` + `persona_constraints`
        + `user_profile` (waga/wzrost/wiek/poziom aktywności/cel — ADR-11, ai-pipeline.md
        §0; brak kompletnego profilu NIE blokuje generowania, tylko ogranicza personalizację)
        + szkielet etapu 1. Retry per-persona osobno.

        Etap 3 — HARMONIZACJA ("zarządca kalendarza", PLANNER_MODEL): wszystkie draft
        `plan_items` naraz -> targeted patche konfliktów (obciążenie, dieta vs trening,
        odpoczynek), cross-referencing notes między personami.

        Konkurencja: każda coroutine bierze WŁASNE połączenie DB (`engine.connect()`,
        nigdy współdzielone), `asyncio.Semaphore` ograniczający równoczesne LLM/DB calls,
        blokujące operacje przez `asyncio.to_thread`.
        """
        raise NotImplementedError(
            "PlanOrchestrator.generate_plan — do zaimplementowania w etapie plan "
            "generation, patrz docs/technical/architecture.md sekcja 4."
        )
