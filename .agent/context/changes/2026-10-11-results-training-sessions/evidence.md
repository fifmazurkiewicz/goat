# Evidence — results training sessions (ADR-25)

| Gate | Command | Outcome |
|---|---|---|
| Backend tests | `cd backend && uv run pytest -q` | 232 passed, 2 failed — both pre-existing on `main` (`test_admin_diagnostics::test_moderation_events_endpoint_is_available`, `test_approval_gate::test_admin_patch_approval_accepts_user`: monkeypatch targets missing in `app.api.routers.admin`) |
| Backend lint | `uv run ruff check .` | 4 errors, all pre-existing in `app/llm/jev.py` (untouched) |
| Backend format | `uv run ruff format --check .` | only `app/llm/jev.py` (pre-existing) |
| Backend types | `uv run mypy app/domain app/llm` | 1 pre-existing error in `app/observability/langfuse.py` (untouched) |
| Frontend | `npm run lint && npm test && npm run build` | lint clean, 174 tests passed, build OK |
| Visual | temporary harness, 390 px + 1280 px | session cards (mobile) / table (desktop) render; empty cells hidden on cards |
| Diagram | `archify finalize dataflow … --quality showcase` | validate / deliver / check / browser-check pass |

Changed surfaces: `results.details` (migration 0018 — run manually by the user), `log_result` tool schema + prompt block `[KOLUMNY WYNIKÓW]`, `GET /personas` `plan_columns`, `GET/POST/PATCH /results` `details`, `/results` UI.

Remaining risks: migration 0018 must be applied before the backend deploy (backend selects `details`); not exercised against a live LLM — whether the model fills `details` consistently needs a real chat check.
