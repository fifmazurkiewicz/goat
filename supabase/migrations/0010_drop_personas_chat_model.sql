-- Chat model is env-driven (`OPENROUTER_CHAT_MODEL`), not per-persona in DB.

alter table public.personas drop column if exists chat_model;