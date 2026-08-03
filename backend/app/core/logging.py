"""Konfiguracja `structlog` + middleware propagujący `request_id` przez `contextvars`.

Patrz docs/technical/architecture.md sekcja 6: JSON w produkcji, ConsoleRenderer
lokalnie; `request_id`/`job_id` przez `contextvars`. Dla background joba (plan
generation) trzeba jawnie zbindować nowy kontekst — kontekst requestu HTTP się nie
propaguje automatycznie do `asyncio.create_task`/`BackgroundTasks`.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


def configure_logging(environment: str = "local") -> None:
    """Wywoływane raz przy starcie aplikacji (`app/main.py`), przed pierwszym loggerem."""
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    renderer = (
        structlog.processors.JSONRenderer()
        if environment == "production"
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generuje/propaguje `request_id` (z nagłówka `X-Request-ID` jeśli obecny),
    bindowany do structlog przez `contextvars` na czas obsługi requestu i zwracany
    w nagłówku odpowiedzi (ułatwia korelację logów klient <-> backend)."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
