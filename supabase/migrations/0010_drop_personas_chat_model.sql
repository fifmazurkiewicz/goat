-- Model czatu jest env-driven (`OPENROUTER_CHAT_MODEL`), nie per-persona w DB.

alter table public.personas drop column if exists chat_model;
