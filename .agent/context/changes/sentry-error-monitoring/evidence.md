# Verification evidence — goat

Reviewed comparison base: `722341830f89590bc866ca479226bc8592f40671`. Implementation is limited to Sentry adapters, entrypoint wiring, failure-safe workflow reporting, SDK dependencies, tests, CI and documentation. Original unrelated local work is excluded; Reelcut uses an isolated copy of origin/main and is never merged into the owner's local checkout.

## Local checks

Backend: **247 passing**. Frontend: 181 Vitest tests + 5 Node privacy tests; lint and Vite production build passed. Mypy passed on 32 source files. Required applicable lint checks passed. Configured backend formatting checks passed.

Focused monitoring command: `cd backend && python -m pytest tests/test_sentry_monitoring.py -q`. Tests use synthetic sentinel content and actual SDK envelopes captured by an in-memory transport; no ingestion call is made. They inspect nested fields/attachments, expected denials/cancellation, duplicate reporting, disabled/invalid configuration, initialization failure and transport outage. Python metrics/log/transaction APIs are explicitly invoked and flushed, asserting zero outgoing envelopes.

## Regression strength

On 2026-11-01 a real Python SDK regression failed while metrics/logs/transactions could bypass the error filter, then passed after explicit dropping callbacks were added. A representative JavaScript filter-removal experiment in TeacherHelper failed its actual-envelope privacy checks, then passed with the original filter restored. These representative mutation checks are not claimed as per-runtime live tests. Each application runs its own intact SDK regression suite.

## Review and limitations

Independent source reviewers: `/root/sdk_backend_final_review` and `/root/sdk_frontend_final_review` (frontend where applicable). Corrective Python review: approve. Frontend review: approve for source integration. Findings and fixes: [canonical decisions](reviews/review-decisions.md); [review report](reviews/implementation-review.md).

Graft runtime was unavailable (`npx --offline @nanonets/graft check`: package not cached), so focused rg/source inspection was used. No paid provider, production user data, hosted ingestion, authenticated source-map upload/resolution, browser-to-Sentry network delivery, APK/device behavior or native-payload acceptance was tested. Aide native crash telemetry stays off. No Render/Vercel variables or production flags were changed. Build upload paths are tested locally without a real token; upload authentication remains an activation gate.

## Publication and CI

Source published to `main`: [a6825eb](https://github.com/fifmazurkiewicz/goat/commit/a6825eb82739ff24f1fc7fb1ca28449b959277d9). Checks for that exact runtime-source commit:

- [CI](https://github.com/fifmazurkiewicz/goat/actions/runs/41356912350): success.

This evidence update changes documentation only. Subsequent automatically triggered documentation-run status is recorded in the final handoff; it is not substituted for the completed source checks.
