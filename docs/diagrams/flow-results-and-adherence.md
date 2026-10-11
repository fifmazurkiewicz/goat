# goat — data flow: workout results and adherence tracking

Interactive, source-linked version (Archify): [`.archify/dataflow-results-adherence-20261011-124302/results-adherence.html`](.archify/dataflow-results-adherence-20261011-124302/results-adherence.html) — editable source: [`candidate.json`](.archify/dataflow-results-adherence-20261011-124302/candidate.json). Regenerate with `node .claude/skills/archify/bin/archify.mjs finalize dataflow <candidate.json> <output.html> --repo-root . --quality showcase`.

```mermaid
flowchart LR
    chat[Chat — Goat or /persona] -->|log_result entries + details| tool[log_result tool]
    cols[(Persona plan columns\npersonas + plan_templates)] -.->|columns in prompt — planned ADR-25| tool
    manual[Add result dialog] -->|POST /results| api[Results API]
    tool -->|insert batch, source=agent| results[(results\nmetric / value / unit + details)]
    api -->|insert / update, source=manual| results
    planItems[(plan_items\ncolumns + rows)] -->|best plan per month| getPlans[GET /plans]
    results -->|own rows, RLS| getResults[GET /results]
    getResults -->|group by day — planned ADR-25| sessions[Results tab\ntraining sessions]
    getResults -->|done days, km| log[Dziennik\n/plans?view=log — ADR-24]
    getPlans -->|planned days| log
```

- **Implemented (ADR-24):** Dziennik — week rows since the first logged result; each day done / planned / missed / off plan; weekly done/planned column; KPI row; persona filter.
- **Planned (ADR-25):** `results.details` with the persona's plan columns; Results tab shows training sessions per day.
