"""Liveness check — bez zależności od bazy/zewnętrznych usług (proste, szybkie 200).

Render Health Check wskazuje na `/api/health` (docs/technical/devops.md sekcja 1).
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
