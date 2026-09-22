# Langfuse tracing and persona-consultation gate

**Status:** Proposed implementation design  
**Date:** 2026-09-23  
**Scope:** FastAPI backend observability and Goat’s general-chat consultation workflow

## Goal

Make every chat turn and plan-generation job inspectable in Langfuse Cloud, including full content, timing, model activity, tool activity, and failures. Prevent Goat from consulting personas until the user explicitly selects which relevant personas may be asked.

## Decisions

- Use Langfuse Cloud in the EU region (`https://cloud.langfuse.com`).
- Store full production trace content: prompts, completions, tool arguments/results, profile/plan context, and coaching outputs. Langfuse credentials remain server-only.
- Langfuse failures must be fail-open: tracing never blocks or fails a chat turn, plan job, SSE stream, or API request.
- A consultation is a two-turn authorization flow. Goat may ask for a choice, but `consult_persona` is unavailable until the user names one or more active personas or explicitly chooses all.
- A request that does not need specialist input is answered directly by Goat. A direct slash conversation remains unchanged.

## Langfuse model

### Trace hierarchy

Each user-visible chat send creates one `chat_turn` trace. The trace contains:

- a root span with the session ID, user UUID, invocation type, and full user message;
- one generation observation for every Goat or trainer model round, with the provider model, complete request/response, token usage, cost, latency, and error;
- tool spans for `get_plan`, `log_result`, `update_user_profile`, `upsert_plan_items`, `rebuild_plan`, and `consult_persona`;
- a nested trainer span/generation for each authorized consultation;
- terminal metadata for completed, cancelled, timed-out, or failed turns.

Each `plan_generate` job creates one `plan_generation` trace. It records queue delay and child spans for coordinator generation, every persona generation (parallel siblings), persistence, Goat harmonization, and final status. The existing plan-job SSE endpoint records the delivery lifecycle as metadata, not a new model generation.

### Instrumentation boundary

`app/observability/langfuse.py` owns client initialization, disabled/no-op behavior, trace/span helpers, and final flush. Domain modules call this facade; they never construct SDK clients directly. `OpenRouterClient` wraps each HTTP model request through the facade so chat, planning, routing, moderation, and title calls receive uniform generation data.

The application lifespan initializes the optional client once and flushes it on shutdown. The facade is configured only when `LANGFUSE_ENABLED=true` and both credentials are present. Missing credentials log one safe startup warning and use no-op observations.

### Configuration

| Key | Default | Purpose |
|---|---|---|
| `LANGFUSE_ENABLED` | `false` | Explicit opt-in per environment |
| `LANGFUSE_PUBLIC_KEY` | unset | Cloud project public key |
| `LANGFUSE_SECRET_KEY` | unset | Cloud project secret key |
| `LANGFUSE_BASE_URL` | `https://cloud.langfuse.com` | EU Cloud endpoint |
| `LANGFUSE_TRACING_ENVIRONMENT` | `ENVIRONMENT` | `local`, `staging`, or `production` |
| `LANGFUSE_TRACING_RELEASE` | app version/git SHA when supplied | Deployment correlation |

No real credentials appear in source control, documentation examples, logs, or trace metadata.

## Persona consultation gate

### State

Create a durable `pending_persona_consultations` record scoped to a general chat session. It stores the assistant message that asked for selection, the relevant active persona IDs/slugs offered to the user, status (`pending`, `authorized`, `expired`, `consumed`), and timestamps.

Only one pending request may exist for a session. A new request replaces an older pending one. A pending request expires after 24 hours or immediately when the active roster no longer contains an offered persona.

### Flow

1. Goat receives a general message.
2. If Goat can answer without specialist input, it answers directly.
3. If specialist input would materially help, Goat calls an internal `request_persona_consultation` action with only relevant active roster members. The action persists the pending request and returns Polish copy naming those choices.
4. The UI renders Goat’s question normally; no trainer runs yet.
5. On the next user message, deterministic selection parsing accepts offered persona names/slugs, or an explicit all-personas phrase. It rejects unknown/inactive personas and ambiguous text.
6. Only a valid selection exposes `consult_persona` to Goat for that turn. The pending request becomes consumed after the turn.
7. If the user declines or changes topic, Goat clears the pending request and continues without consultations.

The model cannot bypass this rule by emitting `consult_persona` early: the backend tool allowlist excludes it unless the current message has a valid authorization.

## Privacy and operations

- Update the privacy notice/consent copy and technical privacy documentation to disclose Langfuse Cloud as a processor of full coaching content, including health-related information.
- Document the required Langfuse Cloud project region, access controls, and retention configuration as a deployment checklist. Retention remains configured in Langfuse Cloud rather than duplicated in the application.
- Add structured logs containing trace IDs and job/session IDs for cross-navigation from Render logs to Langfuse.
- Add a health-safe, non-content diagnostic indicating whether Langfuse is enabled; do not expose credentials or trace data through public APIs.

## Testing

- Unit-test disabled tracing and tracing failures to ensure product actions still succeed.
- Contract-test the trace hierarchy with a fake facade for a chat turn, a nested consultation, and a plan job.
- Test consultation selection: no authorization means no consultation tool; one offered persona; explicit all; unknown persona; stale/expired request; and user decline/change-of-topic.
- Keep the existing chat, plan, privacy, and tool-schema suites green.

## Out of scope

- Frontend/browser telemetry and session replay.
- Langfuse prompt management, datasets, evaluation scores, and model switching.
- Automated selection of all personas or modification of direct `/slug` conversations.
