# Design: month-first Plans and guided generation

**Date:** 2026-09-25  
**Status:** accepted — pending implementation-plan review  
**Canon after implementation:** `docs/technical/frontend.md` and the plan-generation API contract

## Goal

Make Plans a calm, month-first place to see what is scheduled and to start a
coordinated plan. A user selects a day in one monthly calendar, then reads that
day's plan below it. Creating a plan is an explicit four-step dialog in which
the user chooses the period, participating coaches, additional constraints, and
confirms the request.

The page deliberately does **not** track completed work. It shows only the
forward-looking plan.

## Requirements (Given / When / Then)

### GWT-1 — month is the only calendar view

**Given** the user opens `/plans`  
**When** the page loads  
**Then** it shows one monthly calendar, with no Week/Month view switcher  
**And** a day that has one or more plan items has one visual dot  
**And** the dot does not encode persona, category, quantity, or completion.

### GWT-2 — selecting a day reveals its plan

**Given** the monthly calendar is visible  
**When** the user clicks or taps a date  
**Then** that date becomes selected and the page scrolls to its detail below the
calendar  
**And** the URL retains the selected date  
**And** the detail contains only plan sections actually present for that date
(for example Training, Nutrition, or Recovery).

### GWT-3 — daily detail is a coherent combined schedule

**Given** selected coaches have created more than one item for a date  
**When** the day detail is shown  
**Then** the default is `Cały plan`, grouping compatible items by plan category  
**And** each item identifies its responsible coach and retains `Porozmawiaj z trenerem`  
**And** the detail contains no `Zrealizowane` / completed-results panel.

An optional persona tab strip may be shown only when the selected date has
items from multiple personas. `Cały plan` is the default. On touch devices,
horizontal swiping may change the selected persona tab, but visible tabs remain
the accessible, discoverable control.

### GWT-4 — one plan-generation entry point

**Given** a user is on Plans  
**When** no applicable plan exists  
**Then** the header action says `Ułóż plan`  
**When** a plan exists  
**Then** it says `Przebuduj plan`  
**And** either action opens the same centered generation dialog.

### GWT-5 — period choice

**Given** the dialog opens  
**When** the first step is shown  
**Then** it asks `Na jaki okres ułożyć plan?` with `Dzień`, `Tydzień`, and
`Miesiąc`  
**And** choosing a period reveals the matching date input:

| Period | Target selection | Resolved range |
|---|---|---|
| Dzień | one calendar date | that date only |
| Tydzień | any date in a week | Monday through Sunday containing it |
| Miesiąc | a month | first through last calendar day |

### GWT-6 — coach scope

**Given** a period has been selected  
**When** the coach step is shown  
**Then** every active persona is selected by default  
**And** the user can remove personas  
**And** at least one persona is required to continue  
**And** Goat remains the coordinator and final harmonizer, rather than a
user-selectable coach.

### GWT-7 — additional information is a generation instruction

**Given** the user reaches `Dodatkowe informacje`  
**When** they enter optional free text (for example travel, an injury, time
limits, or preferences)  
**Then** it is passed as an explicit instruction to Goat and each selected
persona during plan generation  
**And** it is considered by coordination and final harmonization, not merely
stored for display.

### GWT-8 — editable review before generation

**Given** the user reaches the review step  
**Then** it summarizes period/range, selected coaches, and additional
information  
**And** additional information remains an editable text area in this step  
**And** period and coaches provide compact `Zmień` actions that return to their
respective steps  
**When** the user selects `Ułóż plan`  
**Then** exactly one generation job begins and the existing global progress and
cancellation experience remains available.

### GWT-9 — retired admin diagnostics

**Given** an administrator opens `/admin`  
**Then** they see account management only  
**And** they do not see the deployment-version panel, Moderation, or Audit Log.

The moderation/audit UI, client hooks, read endpoints, and new-event logging
are retired. Existing historical database records are retained, inaccessible
through the product, and are not purged by this work.

## Interaction design

```
Monthly calendar
   └─ select date (dot = at least one item)
       └─ page scrolls to selected-day detail
           ├─ Cały plan (default)
           └─ optional coach tabs / swipe

Ułóż plan / Przebuduj plan
   └─ centered dialog
       1. Dzień | Tydzień | Miesiąc + target date/range
       2. Wybrani trenerzy (all active selected)
       3. Dodatkowe informacje
       4. Review: editable notes + change links → Ułóż plan
```

The dialog stays centered on every breakpoint. On smaller screens it has a
scrollable content area and a persistent footer for Back/Next/Generate.

## Architecture and data flow

### Plans display

`PlansPage` owns the displayed month and selected day from URL search params.
It fetches that month's range, derives dot presence from its items, and passes
the selected day's items to the detail component. The former week agenda,
view-switching state, and results/completion panel are removed from this route.

### Generation request

The API request expands from `{ period_type, start_date }` to include:

```ts
{
  period_type: "day" | "week" | "month";
  start_date: "YYYY-MM-DD";
  persona_ids: string[];
  user_brief?: string;
}
```

The backend validates that every requested persona belongs to the authenticated
user and is active, and rejects an empty selection. It derives the end date:
day = start date; week = Monday–Sunday; month = the full calendar month.

The selected roster and non-empty brief must remain available to the durable
background job, so a restart cannot silently change the requested scope. The
orchestrator generates only for that selected roster, injects `user_brief` into
coordination, persona prompts, and harmonization, and continues to record live
per-persona progress for the selected coaches.

### Error handling

| Situation | Expected behavior |
|---|---|
| no active personas | disable continuing and explain that a coach is required |
| no selected coach | disable Next/Generate; show inline validation |
| inactive/foreign ID submitted | API rejects with a clear validation error |
| active job exists | retain existing 409/idempotent active-job reconciliation |
| dialog closed before Generate | discard local draft; no job is created |
| generation failure/partial success | retain current app-wide progress, cancel, and retry behavior |

## Removals

| Removed | Replacement / reason |
|---|---|
| Week/Month switcher and week agenda | one month-first calendar + selected-day detail |
| `ActualResultsPanel` from Plans | Plans is future-only; Results remains its own destination |
| empty-state week/month generation buttons | one header action and guided dialog |
| Admin deployment-version panel | unnecessary operational panel |
| Admin Moderation and Audit Log panels and read APIs | unused diagnostics retired from the product |

## Tests

- Frontend: a selected day scroll target/detail; one dot for any item; no
Week/Month toggle or completed content; `Cały plan` and persona tab filtering.
- Frontend: dialog validation and navigation across all four steps; all active
personas selected by default; editable notes on review; serialized request.
- Backend: day/week/month range calculation; selected-roster validation;
brief/roster survives the job hand-off; only selected personas are run.
- Backend: existing single-active-job and cancellation behavior remains true.
- Admin: removed diagnostic endpoints are absent/unauthorized as appropriate;
account management stays covered.

## Documentation updates

- `docs/technical/frontend.md` — month-first Plans and four-step dialog.
- `docs/technical/architecture.md` / plan-generation documentation — request
scope, brief propagation, and day period.
- `docs/adr/decisions.md` — decision replacing dual calendar views and making
the planner scope explicit.
