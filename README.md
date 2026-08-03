# Coach — Multi-Persona Coaching App

Aplikacja webowa, w której użytkownik konfiguruje do 5 person-trenerów (dietetyk, trener siłowni, trener badmintona, psycholog sportowy, psycholog, trener motoryczny), rozmawia z nimi w czacie z pamięcią, a agenci zapisują wyniki (siłownia, dieta, basen, triathlon, badminton) do bazy. Persony współpracują przy generowaniu wspólnego, zsynchronizowanego planu tygodnia/miesiąca widocznego w kalendarzu.

## Stack

- **Frontend:** Vite + React + TypeScript + Tailwind + shadcn/ui → Vercel
- **Backend:** Python (FastAPI) → Render
- **DB + Auth:** Supabase (Postgres, RLS, Auth: Google OAuth)
- **LLM:** OpenRouter (structured output przez natywny `response_format: json_schema`)
- **DNS:** Cloudflare

## Dokumentacja

Pełna specyfikacja techniczna, decyzje architektoniczne i plan implementacji — w [`docs/`](docs/):

- [`docs/technical/architecture.md`](docs/technical/architecture.md) — architektura backendu, przepływ czatu (SSE + tool calling), pipeline generowania planu
- [`docs/technical/database-schema.md`](docs/technical/database-schema.md) — pełny schemat bazy danych + RLS
- [`docs/technical/security.md`](docs/technical/security.md) — bezpieczeństwo, jailbreak defense, RLS vs service role
- [`docs/technical/ai-pipeline.md`](docs/technical/ai-pipeline.md) — warstwa AI: modele, moderacja, generowanie planu, testy jakości
- [`docs/technical/frontend.md`](docs/technical/frontend.md) — architektura frontendu, routing, state management, SSE klient
- [`docs/technical/devops.md`](docs/technical/devops.md) — deploy, CI/CD, migracje, sekrety, koszty
- [`docs/technical/cloud-setup.md`](docs/technical/cloud-setup.md) — setup chmury (Supabase / Render / Vercel / Cloudflare) — **aktualna ścieżka**
- [`docs/technical/local-setup.md`](docs/technical/local-setup.md) — lokalny loop (później)
- [`docs/adr/decisions.md`](docs/adr/decisions.md) — log kluczowych decyzji architektonicznych (ADR)

## Status

Implementacja w toku. Szkielet backendu/frontendu (routing, warstwy, DI) gotowy, logika biznesowa
poszczególnych domen (persony, czat, plany, wyniki, admin, katalog ćwiczeń, ustawienia konta)
uzupełniana zgodnie z `docs/adr/decisions.md`.
