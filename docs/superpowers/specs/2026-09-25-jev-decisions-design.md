# Jev Decisions Integration Design

## Goal

Use Jev as an active safety and scope signal for Goat chat responses and proposed plan changes while preserving existing safety overlays, confirmation rules, and tool authorization.

## Boundary

The FastAPI backend calls OpenRouter's Decisions API at `https://openrouter.ai/api/alpha/decisions` with `OPENROUTER_API_KEY` and pinned `typesafe/jev-1.13`. It sends the user request, active hard constraints, and the candidate assistant response or targeted plan patch—never full chat history.

## Flow

1. Before a plan-writing tool result is persisted, evaluate `conflicts_with_hard_constraint` (noul), `needs_medical_or_human_review` (noul), and `request_coverage` (score).
2. A probability of at least 0.80 for either safety noul routes the patch to the existing conservative outcome: do not persist it automatically; return a Polish review/confirmation path. A request-coverage score below the configured threshold preserves the existing ask-for-clarification path.
3. The LLM continues to generate coaching text and plan proposals. Database validation, persona safety overlays, tool permissions, and `rebuild_plan` confirmation continue to decide whether a tool can execute.
4. Failed, malformed, or under-threshold Jev results never grant a write; they use the conservative existing confirmation/clarification route.

## Observability and privacy

Add a decision event to the current audit/observability path with question IDs, answers/probabilities, model/provider/request ID, token usage, latency, final route, and later user correction. Do not duplicate full chat content in decision records; store an input digest and existing entity identifiers.

## Tests

Mock OpenRouter responses. Cover constraint conflict, medical-review signal, low-confidence response, retry exhaustion, and a valid low-risk result. Assert Jev cannot bypass tool permission checks, confirmation requirements, or database validation.

## Non-goals

Jev does not give medical advice, diagnose conditions, generate plans, or override persona safety prompts.
