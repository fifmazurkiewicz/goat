"""Liveness check — no DB / external service dependencies (simple, fast 200).

Render Health Check points to `/api/health` (docs/technical/devops.md section 1).
Body: `{ "status": "ok", "service": "goat" }` (ADR-23).
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "goat"}
