"""Hierarchia wyjątków domenowych + globalne exception handlery.

Zasada z docs/technical/architecture.md sekcja 6 i sekcja 1 (routery "CIENKIE"):
domena/routery rzucają te wyjątki, NIGDY nie łapią ich lokalnie w try/except —
mapowanie na odpowiedź HTTP dzieje się wyłącznie centralnie, tutaj.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


class AppError(Exception):
    """Bazowy wyjątek domenowy. Podklasy nadpisują `http_status`/`code`."""

    http_status: int = 500
    code: str = "internal_error"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.code
        super().__init__(self.message)


class UnauthorizedError(AppError):
    """Brak/nieprawidłowy/wygasły token — 401 (odróżnione od 403 ForbiddenError)."""

    http_status = 401
    code = "unauthorized"


class NotFoundError(AppError):
    http_status = 404
    code = "not_found"


class ForbiddenError(AppError):
    http_status = 403
    code = "forbidden"


class PersonaLimitExceededError(AppError):
    """Limit aktywnych person osiągnięty — per konto (`profiles.max_active_personas`,
    domyślnie 5, edytowalny przez admina), patrz database-schema.md i ADR-12."""

    http_status = 409
    code = "persona_limit_exceeded"


class UsageLimitExceededError(AppError):
    """Limit `usage_limits` (wiadomości/generacje planu) przekroczony — security.md sekcja 4."""

    http_status = 429
    code = "usage_limit_exceeded"


class ModerationRejectedError(AppError):
    """Treść odrzucona przez warstwę B/C moderacji — security.md sekcja 1."""

    http_status = 400
    code = "moderation_rejected"


class ConflictError(AppError):
    http_status = 409
    code = "conflict"


class ExternalServiceError(AppError):
    """Awaria zewnętrznego serwisu (OpenRouter, Supabase Admin API) — 502."""

    http_status = 502
    code = "external_service_error"


def register_exception_handlers(app: FastAPI) -> None:
    """Rejestruje globalne handlery w `main.py` — routery pozostają bez try/except."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.warning("app_error", code=exc.code, message=exc.message, path=request.url.path)
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Pełny traceback tylko do logów (structlog exc_info) — nigdy w treści response.
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
