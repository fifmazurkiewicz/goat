"""Terminal persona failure keeps persisted status and emits a private-safe event."""

import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sentry_sdk

from app.domain.error_reporting import set_error_reporter
from app.domain.plans import orchestrator
from app.monitoring import capture_error, init_sentry
from tests.test_sentry_monitoring import DSN, PRIVATE, MemoryTransport


@pytest.mark.asyncio
async def test_persona_provider_failure_is_reported_once_and_persisted(monkeypatch):
    @asynccontextmanager
    async def connection(claims):
        yield object()

    repo = SimpleNamespace(update_job_persona_status=AsyncMock(), delete_items_for_persona=AsyncMock())
    monkeypatch.setattr(orchestrator, "rls_connection", connection)
    monkeypatch.setattr(orchestrator, "PlansRepo", lambda conn: repo)
    generator = orchestrator.PlanOrchestrator(AsyncMock())
    monkeypatch.setattr(generator, "_generate_for_persona", AsyncMock(side_effect=RuntimeError(PRIVATE)))
    monkeypatch.setenv("SENTRY_ENABLED", "true")
    monkeypatch.setenv("SENTRY_DSN", DSN)
    previous = sentry_sdk.get_client()
    transport = MemoryTransport()
    try:
        assert init_sentry("goat-api", transport=transport)
        set_error_reporter(capture_error)
        await generator._generate_and_persist_persona(
            persona=SimpleNamespace(id="persona"),
            columns=[],
            skeleton={},
            results_summary="",
            user_profile_summary="",
            plan=object(),
            plan_id="plan",
            job_id="job",
            claims={},
            semaphore=asyncio.Semaphore(1),
        )
        repo.update_job_persona_status.assert_awaited_with("job", "persona", "failed", last_error=PRIVATE[:500])
        assert len(transport.envelopes) == 1
        assert PRIVATE not in json.dumps(transport.envelopes[0].get_event())
    finally:
        set_error_reporter(None)
        sentry_sdk.get_client().close()
        sentry_sdk.get_global_scope().set_client(previous)
