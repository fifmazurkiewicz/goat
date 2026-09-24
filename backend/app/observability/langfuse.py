"""Fail-open Langfuse observations for coaching work."""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from functools import lru_cache
from typing import Any

import structlog
from langfuse import Langfuse

from app.core.config import settings

logger = structlog.get_logger(__name__)


@lru_cache
def _client() -> Langfuse | None:
    if not settings.langfuse_enabled:
        return None
    try:
        return Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key.get_secret_value() if settings.langfuse_secret_key else None,
            base_url=settings.langfuse_base_url,
            environment=settings.langfuse_environment or settings.environment,
            release=settings.langfuse_release,
        )
    except Exception as exc:  # telemetry must never stop coaching
        logger.warning("langfuse_initialization_failed", error_type=type(exc).__name__)
        return None


def observe(
    *,
    name: str,
    as_type: str = "span",
    input: Any = None,
    metadata: dict[str, Any] | None = None,
    model: str | None = None,
) -> AbstractContextManager[Any]:
    """Return an SDK context manager, or a no-op when telemetry is unavailable."""
    client = _client()
    if client is None:
        return nullcontext(None)
    try:
        return client.start_as_current_observation(
            name=name, as_type=as_type, input=input, metadata=metadata, model=model
        )
    except Exception as exc:  # telemetry must never stop coaching
        logger.warning("langfuse_observation_start_failed", name=name, error_type=type(exc).__name__)
        return nullcontext(None)


def flush() -> None:
    """Drain queued telemetry during a graceful server shutdown."""
    client = _client()
    if client is None:
        return
    try:
        client.flush()
    except Exception as exc:  # telemetry must never stop shutdown
        logger.warning("langfuse_flush_failed", error_type=type(exc).__name__)


def update(observation: Any, **kwargs: Any) -> None:
    """Best-effort observation update; application work remains independent of telemetry."""
    if observation is None:
        return
    try:
        observation.update(**kwargs)
    except Exception as exc:
        logger.warning("langfuse_observation_update_failed", error_type=type(exc).__name__)
