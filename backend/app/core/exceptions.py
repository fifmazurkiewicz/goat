"""Domain exception hierarchy + global exception handlers.

Rule from docs/technical/architecture.md section 6 and section 1 ("THIN" routers):
domain/routers raise these exceptions, NEVER catch them locally in try/except —
mapping to the HTTP response happens only centrally, here.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


class AppError(Exception):
    """Base domain exception. Subclasses override `http_status`/`code`."""

    http_status: int = 500
    code: str = "internal_error"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.code
        super().__init__(self.message)


class UnauthorizedError(AppError):
    """Missing/invalid/expired token — 401 (distinguished from 403 ForbiddenError)."""

    http_status = 401
    code = "unauthorized"


class NotFoundError(AppError):
    http_status = 404
    code = "not_found"


class ForbiddenError(AppError):
    http_status = 403
    code = "forbidden"


class PersonaLimitExceededError(AppError):
    """Active persona limit reached — per account (`profiles.max_active_personas`,
    default 5, editable by admin), see database-schema.md and ADR-12."""

    http_status = 409
    code = "persona_limit_exceeded"


class UsageLimitExceededError(AppError):
    """`usage_limits` limit (messages/plan generations) exceeded — security.md section 4."""

    http_status = 429
    code = "usage_limit_exceeded"


class ModerationRejectedError(AppError):
    """Content rejected by moderation layer B/C — security.md section 1."""

    http_status = 400
    code = "moderation_rejected"


class ConflictError(AppError):
    http_status = 409
    code = "conflict"


class ValidationError(AppError):
    """Semantic validation outside Pydantic (e.g. `results` entry outside the
    `allowed_metrics` range on manual `POST /results`) — security.md section 3."""

    http_status = 400
    code = "validation_error"


class ExternalServiceError(AppError):
    """External service outage (OpenRouter, Supabase Admin API) — 502."""

    http_status = 502
    code = "external_service_error"


def _format_validation_error(exc: RequestValidationError) -> str:
    """Short message from the first Pydantic error — readable in FE toasts."""
    errors = exc.errors()
    if not errors:
        return "Nieprawidłowe dane wejściowe."
    first = errors[0]
    loc = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
    msg = str(first.get("msg", "nieprawidłowa wartość"))
    return f"{loc}: {msg}" if loc else msg


def register_exception_handlers(app: FastAPI) -> None:
    """Registers global handlers in `main.py` — routers stay without try/except."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.warning("app_error", code=exc.code, message=exc.message, path=request.url.path)
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        message = _format_validation_error(exc)
        logger.warning("validation_error", message=message, path=request.url.path)
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error", "message": message}},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Full traceback only to logs (structlog exc_info) — never in response body.
        logger.error("unhandled_exception", path=request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Wystąpił nieoczekiwany błąd. Spróbuj ponownie później.",
                }
            },
        )
