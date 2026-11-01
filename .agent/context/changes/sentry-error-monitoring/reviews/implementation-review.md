# Implementation review — goat

Comparison base: `722341830f89590bc866ca479226bc8592f40671`. Independent read-only reviews covered the intended diff and new files, actual entrypoints, swallowed failures, SDK filtering, dependency/build boundaries and observed tests. Reviewers did not edit code. Source integration outcome: **approve after the fixes below**. Publication CI and hosted/device acceptance are separate gates.

## Coverage

SENTRY-01–04: covered by reviewed source, examples and local behavioral tests. SENTRY-05: source review and local checks accepted; publication result pending. SENTRY-06: explicitly open. Security/privacy: technical allowlist, EU-only DSNs, explicit opt-in, no non-error products, and no user payloads. Convention alignment: SDK at delivery edges and injected callbacks for domain/application failures. Trading risk logic and original local WIP are preserved.

## Findings and dispositions

### REV-002 — Retain safe source-map Debug IDs

Severity: medium. Preserve validated sourcemap Debug IDs and sanitized matching code_file values; actual SDK envelope and field-filter regressions cover the association. Disposition: [Fix now — verified](review-decisions.md#rev-002).

### REV-003 — Exclude expected JS cancellations

Severity: medium. Drop known cancellation names including DOMException AbortError; real SDK regression expects zero envelopes. Disposition: [Fix now — verified](review-decisions.md#rev-003).

### REV-006 — Observe swallowed goat persona and harmonization failures

Severity: medium. Report at the actual orchestrator catch, using a domain-owned sink. A real persona failure persists failed status and emits one sanitized SDK event. Disposition: [Fix now — verified](review-decisions.md#rev-006).

### REV-007 — Block non-error Python products explicitly

Severity: high. SDK 2.73 ignores enable_metrics=False. Remove it and explicitly drop metrics, logs and transactions. A real flushed-envelope regression failed before this fix and passes after it; each runtime contains the regression. Disposition: [Fix now — verified](review-decisions.md#rev-007).

