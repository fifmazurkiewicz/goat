# Results Training Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Log training results with the logging persona's plan columns (`results.details`) and show them on `/results` as a per-day session list.

**Architecture:** One nullable `jsonb` column on `results` holding an ordered `[{label, value}]` row. The backend validates it (Pydantic), stores it (CAST to jsonb), exposes it, and teaches the chat model the column labels through a prompt block. The frontend groups results by day and renders each day with the existing `PlanItemTable` (table on desktop, cards on mobile, exercise links), so no new table renderer is needed.

**Tech Stack:** FastAPI + Pydantic 2.13 + SQLAlchemy `text()` on asyncpg; React + Vite + TanStack Query + Vitest; Supabase Postgres.

**Spec:** `docs/superpowers/specs/2026-10-11-results-training-sessions-design.md` (ADR-25)

## Global Constraints

- `details` shape: ordered list of `{label, value}`; list length 1–12; `label` trimmed 1–60 chars, unique within the row (case-insensitive); `value` trimmed string 1–120 chars (numbers coerced to strings).
- `metric`, `value`, `unit` stay required on every result; existing charts keep reading them.
- Migration file: `supabase/migrations/0018_result_details.sql` (nullable column, no RLS change).
- asyncpg pattern: jsonb written via `CAST(:param AS jsonb)` + `json.dumps`; jsonb read back may be a `str` → `json.loads`.
- Model-facing copy (tool descriptions, prompt blocks) and UI copy in Polish; code comments/docstrings/docs in English.
- One day = one session (all results of the category on a `logged_date`).
- The model never fabricates values: columns the user did not report are omitted.
- Pre-existing failures to ignore: `tests/test_admin_diagnostics.py::test_moderation_events_endpoint_is_available`, `tests/test_approval_gate.py::test_admin_patch_approval_accepts_user` (fail on the base branch, unrelated).

## Review Focus

- The model sends numbers as `value` (`{"label": "Serie", "value": 3}`) → stored as `"3"`, not rejected (Task 1 test).
- Two labels differing only in case (`Serie`, `serie`) → rejected with a clear error (Task 1 test).
- A persona with no plan template and no column overrides → no columns → no prompt block, and its category keeps the chart view (Task 4 + Task 6 tests).
- A day mixing rows with `details` and legacy rows without → one table with the union of columns; legacy row shows `Ćwiczenie` = metric and `Wynik` = value + unit (Task 6 test).
- asyncpg returns the jsonb column as a JSON string → parsed into a list, not passed as a string to `ResultOut` (Task 2 test).

## Deviation from spec (decided while planning)

- Row editing in the session list reuses the existing `ResultsTable` (value / unit / notes inline edit + delete) inside a collapsible "Edytuj wpisy" per day. Editing `details` cells after saving is not included; a wrong row is deleted and logged again. Spec §4 is updated in Task 9.

---

### Task 1: Migration and `details` DTOs

**Files:**
- Create: `supabase/migrations/0018_result_details.sql`
- Modify: `backend/app/models/schemas.py` (imports; `ResultCreate`, `ResultUpdate`, `ResultOut`, `LogResultEntry` ~lines 371–418)
- Test: `backend/tests/test_result_details.py`

**Interfaces:**
- Produces: `ResultDetailCell(label: str, value: str)`; type alias `ResultDetails = Annotated[list[ResultDetailCell], ...]`; `details: ResultDetails | None` on `ResultCreate`, `ResultUpdate`, `LogResultEntry`; `details: list[ResultDetailCell] | None` on `ResultOut`.

- [ ] **Step 1: Write the failing tests**

```python
"""`results.details` validation (ADR-25) — ordered [{label, value}] keyed by plan columns."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.schemas import LogResultArgs, ResultCreate


def _entry(details: object) -> dict[str, object]:
    return {"category": "strength", "metric": "Dead bug", "value": 50, "date": "2026-10-11", "details": details}


def test_details_accepts_ordered_cells_and_coerces_numbers() -> None:
    parsed = LogResultArgs.model_validate(
        {"entries": [_entry([{"label": " Ćwiczenie ", "value": "Dead bug"}, {"label": "Serie", "value": 3}])]}
    )
    cells = parsed.entries[0].details
    assert cells is not None
    assert [(c.label, c.value) for c in cells] == [("Ćwiczenie", "Dead bug"), ("Serie", "3")]


def test_details_rejects_duplicate_labels_case_insensitive() -> None:
    with pytest.raises(ValidationError):
        LogResultArgs.model_validate(
            {"entries": [_entry([{"label": "Serie", "value": "3"}, {"label": "serie", "value": "4"}])]}
        )


@pytest.mark.parametrize(
    "details",
    [
        [],
        [{"label": "", "value": "x"}],
        [{"label": "x" * 61, "value": "x"}],
        [{"label": "Serie", "value": "   "}],
        [{"label": "Serie", "value": "x" * 121}],
        [{"label": f"k{i}", "value": "v"} for i in range(13)],
    ],
)
def test_details_rejects_invalid_shapes(details: object) -> None:
    with pytest.raises(ValidationError):
        ResultCreate.model_validate(
            {"category": "strength", "metric": "m", "value": 1, "logged_date": "2026-10-11", "details": details}
        )


def test_details_is_optional() -> None:
    parsed = ResultCreate.model_validate({"category": "strength", "metric": "m", "value": 1, "logged_date": "2026-10-11"})
    assert parsed.details is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_result_details.py -v`
Expected: FAIL (`details` is an unknown field / not on the model).

- [ ] **Step 3: Implement**

`supabase/migrations/0018_result_details.sql`:

```sql
-- ADR-25: optional ordered row [{label, value}] keyed by the logging persona's plan columns
-- (`resolve_persona_columns`). Nullable — results without it keep working; no RLS change.
alter table public.results add column if not exists details jsonb;

comment on column public.results.details is
  'Optional ordered row [{label, value}] keyed by the logging persona''s plan columns (ADR-25).';
```

In `backend/app/models/schemas.py`: change imports to

```python
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, computed_field, model_validator
```

Add above `class ResultCreate`:

```python
class ResultDetailCell(BaseModel):
    """One `{label, value}` cell of `results.details` (ADR-25) — label = a plan column."""

    model_config = ConfigDict(str_strip_whitespace=True, coerce_numbers_to_str=True)

    label: str = Field(min_length=1, max_length=60)
    value: str = Field(min_length=1, max_length=120)


def _unique_detail_labels(cells: list[ResultDetailCell]) -> list[ResultDetailCell]:
    labels = [cell.label.casefold() for cell in cells]
    if len(set(labels)) != len(labels):
        raise ValueError("Etykiety w details muszą być unikalne.")
    return cells


ResultDetails = Annotated[
    list[ResultDetailCell],
    Field(min_length=1, max_length=12),
    AfterValidator(_unique_detail_labels),
]
```

Add the field to the models:

```python
# ResultCreate, ResultUpdate, LogResultEntry (after `notes`):
    details: ResultDetails | None = None

# ResultOut (after `notes`):
    details: list[ResultDetailCell] | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_result_details.py tests/test_tool_validation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/0018_result_details.sql backend/app/models/schemas.py backend/tests/test_result_details.py
git commit -m "feat(results): add details column and DTO validation (ADR-25)"
```

---

### Task 2: Persist and return `details` (repo, service, `log_result`, API contract)

**Files:**
- Modify: `backend/app/repositories/results_repo.py` (`_COLUMNS`, `ResultRow`, `_row_to_result`, `create`, `update`)
- Modify: `backend/app/domain/results/service.py` (`log_batch_from_agent` values)
- Modify: `backend/app/domain/chat/orchestrator.py` (~line 762, `log_result` entries)
- Modify: `backend/app/domain/chat/tools.py` (`LOG_RESULT_TOOL_SCHEMA`)
- Test: `backend/tests/test_result_details.py` (append), `backend/tests/test_results_contract.py` (create)

**Interfaces:**
- Consumes: `ResultDetailCell`, `LogResultEntry.details` (Task 1).
- Produces: `ResultRow.details: list[dict[str, str]] | None`; service entries accept key `"details"` (list of dicts or `None`); `GET /api/v1/results` items carry `details`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_result_details.py`:

```python
import json
from datetime import date
from types import SimpleNamespace

from app.domain.chat.tools import LOG_RESULT_TOOL_SCHEMA
from app.domain.results.metrics_cache import AllowedMetricsCache
from app.domain.results.service import ResultsService
from app.repositories.results_repo import _encode_values, _row_to_result


def test_row_to_result_parses_details_json_string() -> None:
    row = SimpleNamespace(
        _mapping={
            "id": "r1", "user_id": "u1", "category": "strength", "metric": "Dead bug", "value": 50,
            "unit": "kg", "logged_date": date(2026, 10, 11), "source": "agent", "source_persona_id": None,
            "is_custom": True, "notes": None, "created_at": date(2026, 10, 11),
            "details": json.dumps([{"label": "Serie", "value": "3"}]),
        }
    )
    assert _row_to_result(row).details == [{"label": "Serie", "value": "3"}]


def test_encode_values_serializes_details_only() -> None:
    encoded = _encode_values({"metric": "m", "details": [{"label": "Serie", "value": "3"}]})
    assert encoded["metric"] == "m"
    assert json.loads(encoded["details"]) == [{"label": "Serie", "value": "3"}]
    assert _encode_values({"details": None})["details"] is None


class _Repo:
    def __init__(self) -> None:
        self.created: list[dict] = []

    async def create(self, user_id: str, values: dict) -> dict:
        self.created.append(values)
        return values


async def test_log_batch_passes_details_through() -> None:
    repo = _Repo()
    service = ResultsService(repo, AllowedMetricsCache())
    cells = [{"label": "Ćwiczenie", "value": "Dead bug"}, {"label": "Serie", "value": "3"}]
    outcomes = await service.log_batch_from_agent(
        user_id="u1",
        source_persona_id="p1",
        entries=[{"category": "strength", "metric": "Dead bug", "value": 50, "unit": "kg",
                  "logged_date": date(2026, 10, 11), "details": cells}],
    )
    assert outcomes[0].ok is True
    assert repo.created[0]["details"] == cells


def test_log_result_tool_schema_exposes_optional_details() -> None:
    entry = LOG_RESULT_TOOL_SCHEMA["function"]["parameters"]["properties"]["entries"]["items"]
    details = entry["properties"]["details"]
    assert details["type"] == "array"
    assert details["items"]["required"] == ["label", "value"]
    assert "details" not in entry["required"]
```

Create `backend/tests/test_results_contract.py`:

```python
"""Contract: `GET /api/v1/results` exposes `details` (ADR-25) — same lesson as the
`tool_calls` hotfix: a DTO field the FE depends on must be pinned by a test."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.repositories.results_repo import ResultRow


@pytest.fixture
def _patched(monkeypatch: pytest.MonkeyPatch):
    @asynccontextmanager
    async def fake_rls(_claims: object):
        yield MagicMock()

    class FakeResultsRepo:
        def __init__(self, _conn: object) -> None:
            pass

        async def list_for_user(self, **_kwargs: object) -> list[ResultRow]:
            return [
                ResultRow(
                    id="r1", user_id="u1", category="strength", metric="Dead bug", value=50.0, unit="kg",
                    logged_date=date(2026, 10, 11), source="agent", source_persona_id="p1", is_custom=True,
                    notes=None, created_at=datetime(2026, 10, 11, tzinfo=UTC),
                    details=[{"label": "Serie", "value": "3"}],
                )
            ]

    monkeypatch.setattr("app.api.routers.results.rls_connection", fake_rls)
    monkeypatch.setattr("app.api.routers.results.ResultsRepo", FakeResultsRepo)

    async def fake_auth() -> object:
        ctx = MagicMock()
        ctx.claims = {"sub": "u1"}
        ctx.user_id = "u1"
        return ctx

    from app.core.security import get_current_user, require_approved, require_health_consent

    for dep in (get_current_user, require_approved, require_health_consent):
        app.dependency_overrides[dep] = fake_auth
    yield
    for dep in (get_current_user, require_approved, require_health_consent):
        app.dependency_overrides.pop(dep, None)


@pytest.mark.asyncio
async def test_results_endpoint_returns_details(_patched) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/results?category=strength")
    assert res.status_code == 200
    assert res.json()[0]["details"] == [{"label": "Serie", "value": "3"}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_result_details.py tests/test_results_contract.py -v`
Expected: FAIL (`_encode_values` missing, `ResultRow` has no `details`, tool schema has no `details`).

- [ ] **Step 3: Implement**

`results_repo.py`:

```python
import json
...
_COLUMNS = (
    "id, user_id, category, metric, value, unit, logged_date, source, source_persona_id, is_custom, notes, "
    "created_at, details"
)
_JSONB_KEYS = ("details",)

# ResultRow: add as the LAST field
    details: list[dict[str, str]] | None = None


def _row_to_result(row: Any) -> ResultRow:
    mapping = normalize_row_mapping(dict(row._mapping), uuid_keys=_UUID_KEYS, float_keys=_FLOAT_KEYS)
    # asyncpg + raw `text()` may hand jsonb back as a JSON string.
    if isinstance(mapping.get("details"), str):
        mapping["details"] = json.loads(mapping["details"])
    return ResultRow(**mapping)


def _sql_param(key: str) -> str:
    # asyncpg does not infer jsonb from a text parameter — explicit CAST (same as personas_repo).
    return f"CAST(:{key} AS jsonb)" if key in _JSONB_KEYS else f":{key}"


def _encode_values(values: dict[str, object]) -> dict[str, object]:
    return {
        key: (json.dumps(value, ensure_ascii=False) if key in _JSONB_KEYS and value is not None else value)
        for key, value in values.items()
    }
```

In `create`: `placeholders = [":user_id", *(_sql_param(key) for key in values.keys())]` and params `{"user_id": user_id, **_encode_values(values)}`.
In `update`: `set_clause = ", ".join(f"{key} = {_sql_param(key)}" for key in values.keys())` and params `{"id": result_id, "user_id": user_id, **_encode_values(values)}`.

`service.py` `log_batch_from_agent` `values` dict: add `"details": entry.get("details"),`. (`create_manual` / `update_manual` already forward the whole payload / updates; `model_dump()` turns cells into dicts.)

`orchestrator.py` `log_result` entries: add

```python
                    "details": [cell.model_dump() for cell in entry.details] if entry.details else None,
```

`tools.py` `LOG_RESULT_TOOL_SCHEMA` entry properties: add after `"notes"`:

```python
                            "details": {
                                "type": "array",
                                "maxItems": 12,
                                "description": (
                                    "Opcjonalnie dla treningu/sesji: wiersz w kolumnach persony z bloku "
                                    "[KOLUMNY WYNIKÓW], w tej samej kolejności. label = dokładna nazwa "
                                    "kolumny, value = to, co user podał (np. '3', '50 / stronę'). Pomiń "
                                    "kolumny, których user nie podał — nie zgaduj."
                                ),
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "label": {"type": "string"},
                                        "value": {"type": "string"},
                                    },
                                    "required": ["label", "value"],
                                    "additionalProperties": False,
                                },
                            },
```

Also extend the tool `description` with one sentence: `"Trening: metric = nazwa ćwiczenia, value = główna liczba (ciężar, powtórzenia lub minuty), a szczegóły w details."`

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_result_details.py tests/test_results_contract.py tests/test_tool_validation.py tests/test_chat_tools_schema.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/results_repo.py backend/app/domain/results/service.py backend/app/domain/chat/orchestrator.py backend/app/domain/chat/tools.py backend/tests/test_result_details.py backend/tests/test_results_contract.py
git commit -m "feat(results): persist and expose details; log_result accepts details (ADR-25)"
```

---

### Task 3: `plan_columns` on `GET /personas`

**Files:**
- Modify: `backend/app/domain/personas/service.py` (add `load_persona_columns` next to `resolve_persona_columns`)
- Modify: `backend/app/models/schemas.py` (`PersonaOut`)
- Modify: `backend/app/api/routers/personas.py` (`list_personas`)
- Test: `backend/tests/test_resolve_persona_columns.py` (append)

**Interfaces:**
- Consumes: `resolve_persona_columns(persona: dict, plan_template: dict | None) -> list[str]` (existing).
- Produces: `async def load_persona_columns(templates_repo: PlanTemplatesListProtocol, personas: Sequence[Any]) -> dict[str, list[str]]` (keyed by persona id; each persona needs `id`, `plan_template_id`, `template_overrides`); `PersonaOut.plan_columns: list[str]` (default `[]`, filled by the list endpoint only).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_resolve_persona_columns.py`:

```python
from types import SimpleNamespace

from app.domain.personas.service import load_persona_columns
from app.models.schemas import PersonaOut


class _Templates:
    def __init__(self) -> None:
        self.calls = 0

    async def list_all(self) -> list[SimpleNamespace]:
        self.calls += 1
        return [SimpleNamespace(id="t1", default_columns=["Ćwiczenie", "Serie"])]


async def test_load_persona_columns_uses_template_overrides_and_missing_template() -> None:
    templates = _Templates()
    personas = [
        SimpleNamespace(id="p1", plan_template_id="t1", template_overrides=None),
        SimpleNamespace(id="p2", plan_template_id="t1", template_overrides={"columns": ["Drill", "Czas"]}),
        SimpleNamespace(id="p3", plan_template_id=None, template_overrides=None),
    ]
    columns = await load_persona_columns(templates, personas)
    assert columns == {"p1": ["Ćwiczenie", "Serie"], "p2": ["Drill", "Czas"], "p3": []}
    assert templates.calls == 1


def test_persona_out_plan_columns_defaults_to_empty() -> None:
    assert PersonaOut.model_fields["plan_columns"].default_factory() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_resolve_persona_columns.py -v`
Expected: FAIL (`load_persona_columns` not defined).

- [ ] **Step 3: Implement**

`personas/service.py` (after `resolve_persona_columns`; add `from collections.abc import Sequence` and `Protocol` to the typing import if missing):

```python
class PlanTemplatesListProtocol(Protocol):
    async def list_all(self) -> list[Any]: ...


async def load_persona_columns(
    templates_repo: PlanTemplatesListProtocol, personas: Sequence[Any]
) -> dict[str, list[str]]:
    """Resolved plan columns per persona id — one template read for the whole list (ADR-25)."""
    templates = {template.id: template for template in await templates_repo.list_all()}
    columns: dict[str, list[str]] = {}
    for persona in personas:
        template = templates.get(persona.plan_template_id) if persona.plan_template_id else None
        columns[persona.id] = resolve_persona_columns(
            {"template_overrides": persona.template_overrides},
            {"default_columns": template.default_columns} if template else None,
        )
    return columns
```

`PersonaOut`: add `plan_columns: list[str] = Field(default_factory=list)` with a comment `# Resolved plan columns (ADR-25) — filled by GET /personas only.`

`personas.py` `list_personas`:

```python
from app.domain.personas.service import PersonaService, load_persona_columns
from app.repositories.templates_repo import PlanTemplatesRepo
...
        rows = await service.list_own(auth.user_id)
        profile = await profiles_repo.get(auth.user_id)
        columns = await load_persona_columns(PlanTemplatesRepo(conn), rows)
    return PersonasListOut(
        items=[
            PersonaOut.model_validate(row).model_copy(update={"plan_columns": columns.get(row.id, [])})
            for row in rows
        ],
        ...
```

Before editing, confirm `PersonaRow` (returned by `list_own`) has `plan_template_id` and `template_overrides` (`backend/app/repositories/personas_repo.py`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_resolve_persona_columns.py tests/test_persona_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/personas/service.py backend/app/models/schemas.py backend/app/api/routers/personas.py backend/tests/test_resolve_persona_columns.py
git commit -m "feat(personas): expose resolved plan_columns on GET /personas (ADR-25)"
```

---

### Task 4: Columns block in the chat prompt

**Files:**
- Modify: `backend/app/domain/chat/context_builder.py` (new `build_result_columns_block`; `build_system_prompt` param)
- Modify: `backend/app/domain/chat/orchestrator.py` (inside the `rls_connection` block ~line 349)
- Test: `backend/tests/test_context_builder.py` (append)

**Interfaces:**
- Consumes: `load_persona_columns` (Task 3), `persona_display_label` (`app/domain/chat/team_lead.py`).
- Produces: `build_result_columns_block(entries: list[tuple[str, list[str]]], *, team_lead: bool) -> str | None`; `ContextBuilder.build_system_prompt(..., result_columns: list[tuple[str, list[str]]] | None = None)`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_context_builder.py`:

```python
from app.domain.chat.context_builder import build_result_columns_block


def test_result_columns_block_for_persona_lists_its_columns() -> None:
    block = build_result_columns_block([("Bartek · Trener motoryczny", ["Ćwiczenie", "Serie"])], team_lead=False)
    assert block is not None
    assert block.startswith("[KOLUMNY WYNIKÓW]")
    assert "Ćwiczenie | Serie" in block
    assert "nie zgaduj" in block


def test_result_columns_block_for_goat_lists_each_persona() -> None:
    block = build_result_columns_block(
        [("Bartek · Trener motoryczny", ["Ćwiczenie", "Serie"]), ("Ola · Trener badmintona", ["Drill", "Czas"])],
        team_lead=True,
    )
    assert block is not None
    assert "- Bartek · Trener motoryczny: Ćwiczenie | Serie" in block
    assert "- Ola · Trener badmintona: Drill | Czas" in block


def test_result_columns_block_omitted_without_columns() -> None:
    assert build_result_columns_block([("Psycholog", [])], team_lead=False) is None
    assert build_result_columns_block([], team_lead=True) is None


def test_system_prompt_includes_result_columns_block() -> None:
    builder = ContextBuilder(_NoopChatRepo(), history_window_messages=10)
    prompt = builder.build_system_prompt(
        persona_type="motor_coach",
        persona_system_prompt="x" * 30,
        persona_constraints=None,
        user_profile=None,
        result_columns=[("Bartek", ["Ćwiczenie", "Serie"])],
    )
    assert "[KOLUMNY WYNIKÓW]" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_context_builder.py -v`
Expected: FAIL (`build_result_columns_block` not defined).

- [ ] **Step 3: Implement**

`context_builder.py` (next to `build_recent_results_block`):

```python
def build_result_columns_block(entries: list[tuple[str, list[str]]], *, team_lead: bool) -> str | None:
    """Plan columns the model must use for `log_result.details` (ADR-25)."""
    entries = [(label, columns) for label, columns in entries if columns]
    if not entries:
        return None
    rule = (
        "Pomiń kolumny, których user nie podał — nie zgaduj. Etykiety (label) przepisuj dokładnie, "
        "w tej kolejności."
    )
    if team_lead:
        lines = [f"- {label}: {' | '.join(columns)}" for label, columns in entries]
        return (
            "[KOLUMNY WYNIKÓW]\nGdy zapisujesz trening przez log_result, wypełnij `details` kolumnami "
            f"persony, której dziedziny dotyczy wynik. {rule}\n" + "\n".join(lines)
        )
    return (
        "[KOLUMNY WYNIKÓW]\nGdy zapisujesz trening przez log_result, wypełnij `details` tymi kolumnami. "
        f"{rule}\n{' | '.join(entries[0][1])}"
    )
```

`build_system_prompt`: new keyword param `result_columns: list[tuple[str, list[str]]] | None = None`; after the plan block:

```python
        columns_block = build_result_columns_block(result_columns or [], team_lead=persona_type == "team_lead")
        if columns_block:
            segments.append(columns_block)
```

`orchestrator.py` — imports `from app.domain.personas.service import load_persona_columns` and `from app.repositories.templates_repo import PlanTemplatesRepo` (if not already imported; `persona_display_label` is already imported from `team_lead`). Inside the `async with rls_connection(self._claims) as conn:` block, before `build_system_prompt`:

```python
            result_columns: list[tuple[str, list[str]]] = []
            # Consulted personas get read-only tools (no log_result) — no columns block.
            if not consult_read_only:
                column_personas = list(self._consult_roster or []) if persona.type == "team_lead" else [persona]
                if column_personas:
                    columns_by_id = await load_persona_columns(PlanTemplatesRepo(conn), column_personas)
                    result_columns = [
                        (persona_display_label(p), columns_by_id.get(p.id, [])) for p in column_personas
                    ]
```

and pass `result_columns=result_columns` to `build_system_prompt`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_context_builder.py tests/test_run_chat_turn_goat.py tests/test_orchestrator_team_lead.py tests/test_consult_persona.py -v`
Expected: PASS (if orchestrator tests use fakes without `plan_template_id`, give the fakes `plan_template_id=None, template_overrides=None` rather than weakening the code).

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/chat/context_builder.py backend/app/domain/chat/orchestrator.py backend/tests/test_context_builder.py
git commit -m "feat(chat): teach log_result the persona plan columns via prompt block (ADR-25)"
```

---

### Task 5: Backend gates

- [ ] **Step 1:** `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app/domain app/llm && uv run pytest -q`
Expected: all clean; pytest only the two pre-existing admin failures listed in Global Constraints.
- [ ] **Step 2:** Fix anything found, commit `chore(backend): lint/format fixes` if needed.

---

### Task 6: Frontend types and session grouping

**Files:**
- Modify: `frontend/src/types/api.ts` (`Result`, `Persona`)
- Modify: `frontend/src/hooks/useResults.ts` (`ResultCreateInput`)
- Create: `frontend/src/lib/training-sessions.ts`
- Test: `frontend/src/lib/training-sessions.test.ts`

**Interfaces:**
- Produces:
  - `interface ResultDetailCell { label: string; value: string }`; `Result.details: ResultDetailCell[] | null`; `Persona.plan_columns?: string[]`; `ResultCreateInput.details?: ResultDetailCell[] | null`.
  - `interface TrainingSession { date: string; results: Result[]; personaIds: (string | null)[]; content: PlanItemContent }`
  - `buildTrainingSessions(results: Result[]): TrainingSession[]` — newest day first; within a day oldest entry first.
  - `sessionPersonasForCategory(personas: Persona[], category: ResultCategory): Persona[]` — active personas mapped to the category with non-empty `plan_columns`.

- [ ] **Step 1: Write the failing tests**

```ts
import { describe, expect, it } from "vitest";

import { buildTrainingSessions, sessionPersonasForCategory } from "@/lib/training-sessions";
import type { Persona, Result } from "@/types/api";

function result(overrides: Partial<Result>): Result {
  return {
    id: "r", user_id: "u1", category: "strength", metric: "Dead bug", value: 50, unit: "kg",
    logged_date: "2026-10-11", source: "agent", source_persona_id: "p1", is_custom: true,
    notes: null, details: null, created_at: "2026-10-11T10:00:00Z", ...overrides,
  };
}

describe("buildTrainingSessions", () => {
  it("groups by day, newest day first, entries in logging order", () => {
    const sessions = buildTrainingSessions([
      result({ id: "a", logged_date: "2026-10-10" }),
      result({ id: "c", created_at: "2026-10-11T12:00:00Z" }),
      result({ id: "b", created_at: "2026-10-11T09:00:00Z" }),
    ]);
    expect(sessions.map((s) => s.date)).toEqual(["2026-10-11", "2026-10-10"]);
    expect(sessions[0].results.map((r) => r.id)).toEqual(["b", "c"]);
  });

  it("builds one table with the union of labels; legacy rows fall back to Ćwiczenie + Wynik", () => {
    const [session] = buildTrainingSessions([
      result({ id: "a", details: [{ label: "Ćwiczenie", value: "Dead bug" }, { label: "Serie", value: "3" }] }),
      result({ id: "b", metric: "weight_kg", value: 82.5, unit: "kg", details: null, created_at: "2026-10-11T11:00:00Z" }),
    ]);
    expect(session.content.columns).toEqual(["Ćwiczenie", "Serie", "Wynik"]);
    expect(session.content.rows).toEqual([
      ["Dead bug", "3", ""],
      ["weight_kg", "", "82,5 kg"],
    ]);
  });

  it("adds notes as an Uwagi column", () => {
    const [session] = buildTrainingSessions([
      result({ details: [{ label: "Serie", value: "3" }], notes: "lewa strona słabsza" }),
    ]);
    expect(session.content.columns).toEqual(["Serie", "Uwagi"]);
    expect(session.content.rows).toEqual([["3", "lewa strona słabsza"]]);
  });

  it("keeps Goat entries (source_persona_id null) in the day's personas", () => {
    const [session] = buildTrainingSessions([result({ source_persona_id: null })]);
    expect(session.personaIds).toEqual([null]);
  });
});

describe("sessionPersonasForCategory", () => {
  const base = { active: true, custom_result_category: null, plan_columns: ["Ćwiczenie"] } as Partial<Persona>;
  it("returns active personas of the category that have plan columns", () => {
    const personas = [
      { ...base, id: "t", type: "motor_coach" },
      { ...base, id: "d", type: "dietitian" },
      { ...base, id: "x", type: "personal_trainer", active: false },
      { ...base, id: "y", type: "personal_trainer", plan_columns: [] },
    ] as Persona[];
    expect(sessionPersonasForCategory(personas, "strength").map((p) => p.id)).toEqual(["t"]);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/lib/training-sessions.test.ts`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement**

`types/api.ts`:

```ts
/** One `{label, value}` cell of `results.details` (ADR-25) — label = a plan column. */
export interface ResultDetailCell {
  label: string;
  value: string;
}
// Result: add after `notes`
  details: ResultDetailCell[] | null;
// Persona: add after `active`
  /** Resolved plan columns (ADR-25) — present on `GET /personas` items. */
  plan_columns?: string[];
```

`useResults.ts` `ResultCreateInput`: add `details?: ResultDetailCell[] | null;` (import the type).

`lib/training-sessions.ts`:

```ts
import { personaResultCategory } from "@/lib/result-categories";
import type { Persona, PlanItemContent, Result, ResultCategory, ResultDetailCell } from "@/types/api";

const EXERCISE_LABEL = "Ćwiczenie";
const RESULT_LABEL = "Wynik";
const NOTES_LABEL = "Uwagi";

export interface TrainingSession {
  date: string;
  results: Result[];
  personaIds: (string | null)[];
  content: PlanItemContent;
}

function formatValue(value: number): string {
  return String(value).replace(".", ",");
}

/** Row cells for one result — `details` as logged, else a legacy fallback (metric + value). */
function resultCells(result: Result): ResultDetailCell[] {
  const cells = result.details?.length
    ? [...result.details]
    : [
        { label: EXERCISE_LABEL, value: result.metric },
        { label: RESULT_LABEL, value: `${formatValue(result.value)} ${result.unit ?? ""}`.trim() },
      ];
  if (result.notes && !cells.some((cell) => cell.label === NOTES_LABEL)) {
    cells.push({ label: NOTES_LABEL, value: result.notes });
  }
  return cells;
}

/** One day = one session (ADR-25): newest day first, entries in logging order. */
export function buildTrainingSessions(results: Result[]): TrainingSession[] {
  const byDate = new Map<string, Result[]>();
  for (const result of results) {
    byDate.set(result.logged_date, [...(byDate.get(result.logged_date) ?? []), result]);
  }
  return [...byDate.entries()]
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([date, dayResults]) => {
      const ordered = [...dayResults].sort((a, b) => a.created_at.localeCompare(b.created_at));
      const rowsCells = ordered.map(resultCells);
      const columns: string[] = [];
      for (const cells of rowsCells) {
        for (const cell of cells) if (!columns.includes(cell.label)) columns.push(cell.label);
      }
      // Notes last, whatever order the rows introduced it in.
      if (columns.includes(NOTES_LABEL)) columns.push(...columns.splice(columns.indexOf(NOTES_LABEL), 1));
      const rows = rowsCells.map((cells) =>
        columns.map((label) => cells.find((cell) => cell.label === label)?.value ?? "")
      );
      return {
        date,
        results: ordered,
        personaIds: [...new Set(ordered.map((r) => r.source_persona_id))],
        content: { title: date, columns, rows, notes: null },
      };
    });
}

/** Active personas logging into `category` that have plan columns — the session view applies. */
export function sessionPersonasForCategory(personas: Persona[], category: ResultCategory): Persona[] {
  return personas.filter(
    (persona) =>
      persona.active && personaResultCategory(persona) === category && (persona.plan_columns?.length ?? 0) > 0
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib/training-sessions.test.ts`
Expected: PASS. Then `npm run lint` and `npx tsc -p tsconfig.app.json --noEmit` (or `npm run build`) — fix any test fixtures that construct `Result` without `details` by adding `details: null`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/hooks/useResults.ts frontend/src/lib/training-sessions.ts frontend/src/lib/training-sessions.test.ts
git commit -m "feat(results-ui): training session grouping and details types (ADR-25)"
```

---

### Task 7: Session list on `/results`

**Files:**
- Create: `frontend/src/components/results/TrainingSessionList.tsx`
- Modify: `frontend/src/pages/ResultsPage.tsx`
- Test: `frontend/src/components/results/TrainingSessionList.test.tsx`

**Interfaces:**
- Consumes: `buildTrainingSessions`, `sessionPersonasForCategory` (Task 6); `PlanItemTable({content, variant?})`; `ResultsTable({results, category})`.
- Produces: `TrainingSessionList({ results: Result[]; personas: Persona[]; category: ResultCategory })`.

- [ ] **Step 1: Write the failing test**

Same providers/mocks as `src/components/plans/PlanItemTable.test.tsx`; `ResultsTable` mutations are mocked so no QueryClient is needed:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { TrainingSessionList } from "@/components/results/TrainingSessionList";
import type { Persona, Result } from "@/types/api";

vi.mock("@/hooks/useExercises", () => ({ useExercises: () => ({ data: [] }) }));
vi.mock("@/hooks/useResults", () => ({
  useUpdateResult: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteResult: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

function result(overrides: Partial<Result>): Result {
  return {
    id: "r", user_id: "u1", category: "strength", metric: "Dead bug", value: 50, unit: "kg",
    logged_date: "2026-10-11", source: "agent", source_persona_id: "p1", is_custom: true,
    notes: null, details: null, created_at: "2026-10-11T10:00:00Z", ...overrides,
  };
}

const personas = [{ id: "p1", name: "Bartek" }] as Persona[];

function renderList(results: Result[]) {
  return render(
    <MemoryRouter>
      <TrainingSessionList results={results} personas={personas} category="strength" />
    </MemoryRouter>
  );
}

describe("TrainingSessionList", () => {
  it("renders one card per day with exercise rows", () => {
    renderList([
      result({ id: "a", details: [{ label: "Ćwiczenie", value: "Dead bug" }, { label: "Serie", value: "3" }] }),
      result({ id: "b", logged_date: "2026-10-10", source_persona_id: null }),
    ]);
    expect(screen.getByRole("heading", { name: /11 października 2026/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /10 października 2026/i })).toBeInTheDocument();
    expect(screen.getAllByText("Dead bug").length).toBeGreaterThan(0);
    expect(screen.getByText(/Bartek/)).toBeInTheDocument();
    expect(screen.getByText(/Goat/)).toBeInTheDocument();
  });

  it("shows the empty state without results", () => {
    renderList([]);
    expect(
      screen.getByText("Brak zapisanych sesji — zgłoś trening w czacie albo dodaj go ręcznie.")
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/results/TrainingSessionList.test.tsx`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement**

`TrainingSessionList.tsx`:

```tsx
import { useMemo } from "react";
import { format, parseISO } from "date-fns";
import { pl } from "date-fns/locale";

import { PlanItemTable } from "@/components/plans/PlanItemTable";
import { ResultsTable } from "@/components/results/ResultsTable";
import { buildTrainingSessions } from "@/lib/training-sessions";
import type { Persona, Result, ResultCategory } from "@/types/api";

interface TrainingSessionListProps {
  results: Result[];
  personas: Persona[];
  category: ResultCategory;
}

/**
 * `/results` training categories (ADR-25): one card per day, rows from `results.details`
 * rendered by `PlanItemTable` (table on desktop, cards on mobile, catalog links). Editing
 * reuses `ResultsTable` inside a collapsible section.
 */
export function TrainingSessionList({ results, personas, category }: TrainingSessionListProps) {
  const sessions = useMemo(() => buildTrainingSessions(results), [results]);
  const personaName = useMemo(() => new Map(personas.map((p) => [p.id, p.name])), [personas]);

  if (sessions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Brak zapisanych sesji — zgłoś trening w czacie albo dodaj go ręcznie.
      </p>
    );
  }

  return (
    <ul className="space-y-4" aria-label="Sesje treningowe">
      {sessions.map((session) => {
        const who = session.personaIds.map((id) => (id ? (personaName.get(id) ?? "Persona") : "Goat"));
        return (
          <li key={session.date} className="rounded-lg border bg-card p-4">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-base font-semibold first-letter:uppercase">
                {format(parseISO(session.date), "EEEE, d MMMM yyyy", { locale: pl })}
              </h2>
              <p className="text-xs text-muted-foreground">
                {session.results.length} {session.results.length === 1 ? "wpis" : "wpisy"} · {[...new Set(who)].join(", ")}
              </p>
            </div>
            <PlanItemTable content={session.content} />
            <details className="mt-3">
              <summary className="cursor-pointer text-sm text-muted-foreground hover:text-foreground">
                Edytuj wpisy
              </summary>
              <div className="mt-2">
                <ResultsTable results={session.results} category={category} />
              </div>
            </details>
          </li>
        );
      })}
    </ul>
  );
}
```

(Polish plural: use `wpis` / `wpisy` (2–4) / `wpisów` (5+) — add a tiny helper `entriesLabel(n)` in the same file: `n === 1 ? "wpis" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? "wpisy" : "wpisów"`.)

`ResultsPage.tsx`:
- `const personas = personasData?.items ?? [];`
- `const sessionPersonas = useMemo(() => (activeCategory ? sessionPersonasForCategory(personas, activeCategory) : []), [personas, activeCategory]);`
- In the content branch: `sessionPersonas.length > 0 ? <TrainingSessionList results={results ?? []} personas={personas} category={activeCategory} /> : (existing Trend card + ResultsTable)`.
- Pass `personas={sessionPersonas}` to `AddResultDialog` (Task 8).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/results src/lib/training-sessions.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/results/TrainingSessionList.tsx frontend/src/components/results/TrainingSessionList.test.tsx frontend/src/pages/ResultsPage.tsx
git commit -m "feat(results-ui): training session list for categories with plan columns (ADR-25)"
```

---

### Task 8: Manual entry with persona columns

**Files:**
- Modify: `frontend/src/components/results/AddResultDialog.tsx`
- Create: `frontend/src/lib/result-details-form.ts` (pure helper)
- Test: `frontend/src/lib/result-details-form.test.ts`

**Interfaces:**
- Consumes: `findExerciseColumnIndex(columns: string[]): number` (`lib/exercise-matcher.ts`), `ResultDetailCell`.
- Produces: `buildDetailsFromInputs(columns: string[], values: string[]): { details: ResultDetailCell[] | null; exercise: string }`; `AddResultDialog({ category, personas?: Persona[] })`.

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";

import { buildDetailsFromInputs } from "@/lib/result-details-form";

describe("buildDetailsFromInputs", () => {
  it("keeps filled columns in order and returns the exercise cell", () => {
    expect(buildDetailsFromInputs(["Ćwiczenie", "Serie", "Ciężar (kg)"], ["Dead bug ", "", "50 / stronę"])).toEqual({
      details: [
        { label: "Ćwiczenie", value: "Dead bug" },
        { label: "Ciężar (kg)", value: "50 / stronę" },
      ],
      exercise: "Dead bug",
    });
  });

  it("returns null details when nothing is filled", () => {
    expect(buildDetailsFromInputs(["Ćwiczenie"], ["  "])).toEqual({ details: null, exercise: "" });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/result-details-form.test.ts`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement**

`lib/result-details-form.ts`:

```ts
import { findExerciseColumnIndex } from "@/lib/exercise-matcher";
import type { ResultDetailCell } from "@/types/api";

/** Manual entry → `details` (ADR-25): filled columns in plan order + the exercise cell for `metric`. */
export function buildDetailsFromInputs(
  columns: string[],
  values: string[]
): { details: ResultDetailCell[] | null; exercise: string } {
  const cells = columns
    .map((label, index) => ({ label, value: (values[index] ?? "").trim() }))
    .filter((cell) => cell.value !== "");
  const exercise = (values[findExerciseColumnIndex(columns)] ?? "").trim();
  return { details: cells.length ? cells : null, exercise };
}
```

`AddResultDialog.tsx`:
- Props: `personas?: Persona[]` (default `[]`).
- Schema: `metric: z.string().trim()` (no `min(1)`; required-ness checked in `onSubmit`).
- State: `const [personaId, setPersonaId] = useState<string | null>(null); const persona = personas.find((p) => p.id === personaId) ?? personas[0] ?? null; const columns = persona?.plan_columns ?? []; const [columnValues, setColumnValues] = useState<string[]>([]);` — reset `columnValues` to `[]` when the persona changes.
- When `columns.length > 0`, render above "Metryka": a persona `Select` (only if `personas.length > 1`, label "Persona"), then one `Input` per column (`id={`detail-${index}`}`, `Label` = column name), `grid sm:grid-cols-2 gap-3`.
- `onSubmit`:

```ts
    const { details, exercise } = buildDetailsFromInputs(columns, columnValues);
    const metric = values.metric || exercise;
    if (!metric) {
      form.setError("metric", { message: "Podaj nazwę metryki lub ćwiczenia" });
      return;
    }
    await createResult.mutateAsync({ ...values, metric, category, notes: values.notes || null, details });
```

- Metric placeholder when columns exist: `"domyślnie: nazwa ćwiczenia"`.
- After success also `setColumnValues([])`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib/result-details-form.test.ts && npm run lint`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/result-details-form.ts frontend/src/lib/result-details-form.test.ts frontend/src/components/results/AddResultDialog.tsx frontend/src/pages/ResultsPage.tsx
git commit -m "feat(results-ui): manual result entry with persona plan columns (ADR-25)"
```

---

### Task 9: Docs, gates, visual check

**Files:**
- Modify: `docs/technical/database-schema.md` (results table: `details jsonb` row + shape)
- Modify: `docs/technical/frontend.md` §6 (session list tree from spec §4, with the editing deviation)
- Modify: `docs/technical/ai-pipeline.md` §2 (`log_result.details`, `[KOLUMNY WYNIKÓW]` block)
- Modify: `docs/adr/decisions.md` ADR-25 status → `accepted (2026-10-11, implemented)`; add the editing deviation to Consequences
- Modify: `docs/superpowers/specs/2026-10-11-results-training-sessions-design.md` (status → implemented; §4 editing note)
- Modify: `AGENTS.md` (Learned Workspace Facts: migration `0018_result_details.sql`; ADR-25 now accepted)
- Modify: `docs/diagrams/.archify/dataflow-results-adherence-*/candidate.json` — drop "(planned)" labels, re-run `finalize` (with `ARCHIFY_CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`); update the Mermaid in `docs/diagrams/flow-results-and-adherence.md`.

- [ ] **Step 1:** Update the docs above.
- [ ] **Step 2:** Backend gates: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app/domain app/llm && uv run pytest -q` (only the two pre-existing admin failures).
- [ ] **Step 3:** Frontend gates: `cd frontend && npm run lint && npm test && npm run build`.
- [ ] **Step 4:** Visual check: render `TrainingSessionList` with sample data at 390 px and 1280 px (temporary harness, deleted afterwards), confirm the table/cards and the empty state.
- [ ] **Step 5:** Commit `docs: ADR-25 implemented — results details, session list` and push the branch.
