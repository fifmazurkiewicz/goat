"""Admin diagnostics repositories normalize database rows into JSON-safe values.

The `/admin/moderation-events`, `/admin/audit-log` and `/admin/deploy-info` endpoints were
removed in 67c4cfa (month-calendar rebuild); the repositories remain."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.repositories.admin_audit_repo import AdminAuditRepo


class _Result:
    def __init__(self, row: object) -> None:
        self._row = row

    def all(self) -> list[object]:
        return [self._row]

    def __iter__(self):
        return iter([self._row])


class _Connection:
    async def execute(self, *_args: object, **_kwargs: object) -> _Result:
        return _Result(
            SimpleNamespace(
                _mapping={
                    "id": UUID("00000000-0000-0000-0000-000000000001"),
                    "admin_user_id": UUID("00000000-0000-0000-0000-000000000002"),
                    "action": "edit_approval",
                    "target_user_id": UUID("00000000-0000-0000-0000-000000000003"),
                    "details": None,
                    "created_at": datetime(2026, 9, 24, tzinfo=UTC),
                }
            )
        )


@pytest.mark.asyncio
async def test_audit_repo_normalizes_uuid_columns() -> None:
    entry = (await AdminAuditRepo(_Connection()).list_all())[0]
    assert entry.id == "00000000-0000-0000-0000-000000000001"
    assert entry.target_user_id == "00000000-0000-0000-0000-000000000003"
