"""Router `/admin` — wyłącznie `service_role` + jawna, kodowa weryfikacja `profiles.is_admin`.

"Ukrycie w UI to nie jest autoryzacja" — docs/technical/security.md sekcja 2 i
docs/technical/architecture.md sekcja 2. Zależność `require_admin` (TODO, patrz
`app/core/security.py`) rzuca `NotImplementedError` do czasu powstania `ProfilesRepo`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import AuthContext, require_admin
from app.models.schemas import AdminUserOut, PersonaLimitUpdate

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-log")
async def list_audit_log(auth: AuthContext = Depends(require_admin)) -> list[dict]:
    # TODO: pełna implementacja — patrz docs/technical/architecture.md i
    # docs/technical/database-schema.md (tabela admin_audit_log).
    return []


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(auth: AuthContext = Depends(require_admin)) -> list[AdminUserOut]:
    # TODO: rls_connection z service_role (architecture.md sekcja 2) ->
    # ProfilesRepo(conn).list_all(), zmapować ProfileRow -> AdminUserOut.
    return []


@router.patch("/users/{user_id}/persona-limit", response_model=AdminUserOut)
async def update_persona_limit(
    user_id: str,
    payload: PersonaLimitUpdate,
    auth: AuthContext = Depends(require_admin),
) -> AdminUserOut:
    """Ustawia `profiles.max_active_personas` per konto (ADR-12) — zastępuje globalną
    stałą "5". Trigger DB (`enforce_persona_limit`) pozostaje ostateczną linią obrony
    niezależnie od tego ustawienia.

    TODO pełna implementacja:
    1. `ProfilesRepo(conn).update_max_active_personas(user_id, payload.max_active_personas)`
       (service_role connection — admin operuje na cudzym koncie, poza zasięgiem RLS usera).
    2. Zapis `admin_audit_log` w TEJ SAMEJ transakcji: `action='edit_persona_limit'`,
       `admin_user_id=auth.user_id`, `target_user_id=user_id`,
       `details={"max_active_personas": payload.max_active_personas}`.
    """
    raise NotImplementedError(
        "update_persona_limit — do zaimplementowania w etapie admin, patrz "
        "docs/adr/decisions.md ADR-12."
    )
