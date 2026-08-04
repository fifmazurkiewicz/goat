"""Router `/auth` — lokalny login email/hasło (tylko `ENVIRONMENT=local`)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.core.db import service_role_connection
from app.core.dev_auth import (
    bootstrap_dev_user,
    create_local_access_token,
    verify_dev_credentials,
)
from app.core.exceptions import NotFoundError, UnauthorizedError
from app.models.schemas import DevLoginRequest, DevLoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/dev-login", response_model=DevLoginResponse)
async def dev_login(payload: DevLoginRequest) -> DevLoginResponse:
    if not settings.dev_auth_enabled:
        raise NotFoundError("Endpoint dostępny wyłącznie lokalnie.")

    if not verify_dev_credentials(payload.email, payload.password):
        raise UnauthorizedError("Nieprawidłowy email lub hasło.")

    user_id = settings.dev_auth_user_id
    email = settings.dev_auth_email or payload.email

    async with service_role_connection() as conn:
        await bootstrap_dev_user(conn, user_id, email)

    token = create_local_access_token(user_id, email)
    return DevLoginResponse(access_token=token, user_id=user_id, email=email)
