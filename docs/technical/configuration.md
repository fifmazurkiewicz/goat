# Environment variable names

Infer configuration from `.env.example` files — never from local `.env`. Placeholders only; no production values.

Templates:

- Root `.env.example` — backend-oriented copy-paste helper
- `backend/.env.example` — API process
- `frontend/.env.example` — Vite (`frontend/.env.local`)

Setup: [`local-setup.md`](local-setup.md). Hosting: [`devops.md`](devops.md) §5.

## Backend (`backend/.env`)

| Name | Role |
|---|---|
| `ENVIRONMENT` | `local` enables email/password dev auth; production requires Supabase |
| `DATABASE_URL` | `postgresql+asyncpg://…` — local `localhost:5432/goat`; Render uses Supavisor `:6543` |
| `DEV_AUTH_EMAIL` / `DEV_AUTH_PASSWORD` / `DEV_AUTH_USER_ID` | Local login only |
| `LOCAL_JWT_SECRET` | Signs local JWTs |
| `SUPABASE_URL` | Required in production; also used by photo import |
| `SUPABASE_JWKS_URL` | JWT verification (not supabase-py) |
| `SUPABASE_SERVICE_ROLE_KEY` | Admin API / import — backend only |
| `OPENROUTER_API_KEY` | LLM |
| `OPENROUTER_CHAT_MODEL` | Chat + default planner |
| `OPENROUTER_PLANNER_MODEL` | Empty = same as chat |
| `OPENROUTER_CHAT_MODEL_FALLBACKS` | OpenRouter fallback list (optional; has a code default) |
| `CORS_ORIGINS` | Comma-separated; local default `http://localhost:3000` |
| `ADMIN_EMAILS` | Extra auto-approve emails on profile INSERT (ADR-22); sole admin is always included |
| `CHAT_LLM_TITLE_ENABLED` | Conversation auto-title |
| `PLAN_AUTO_HARMONIZE_ON_UPSERT` | Harmonize after upsert |
| `CHAT_HARD_TIMEOUT_S` | Whole SSE turn (default 210) |
| `CHAT_ROUND_TIMEOUT_S` | Per LLM round (default 90) |
| `PRIVACY_CHAT_RETENTION_DAYS` | Inactive chat-session retention (default 365 days) |
| `PRIVACY_COMPLETED_JOB_RETENTION_DAYS` | Completed background and plan-job retention (default 30 days) |
| `PRIVACY_MODERATION_SNIPPET_RETENTION_DAYS` | Raw moderation-snippet retention before redaction (default 90 days) |

## Frontend (`frontend/.env.local`)

| Name | Role |
|---|---|
| `VITE_ENABLE_DEV_LOGIN` | `true` locally; off on Vercel |
| `VITE_API_BASE_URL` | Render/API origin (`http://localhost:8000` locally) |
| `VITE_SUPABASE_URL` | Required on Vercel (OAuth) |
| `VITE_SUPABASE_ANON_KEY` | Public anon key (RLS) |

`PHOTO_STORAGE_ROOT` is a code constant (`exercise`), not an env var.
