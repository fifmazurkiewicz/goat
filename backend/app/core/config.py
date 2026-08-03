"""Konfiguracja aplikacji z env — patrz `.env.example` i docs/technical/devops.md sekcja 5."""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"

    database_url: str
    supabase_url: str
    supabase_jwks_url: str
    supabase_service_role_key: SecretStr

    openrouter_api_key: SecretStr
    openrouter_chat_model: str = "anthropic/claude-haiku-4.5"
    openrouter_planner_model: str = "anthropic/claude-sonnet-4.6"
    # Fallback providerzy dla chat_model (ai-pipeline.md §1) — awaria jednego providera
    # nie wywala czatu. Przekazywane jako `extra_body={"models": [...]}` do OpenRoutera.
    openrouter_chat_model_fallbacks: str = "openai/gpt-5-mini"

    # Comma-separated string (format env var) — patrz cors_origins_list poniżej.
    cors_origins: str = "http://localhost:3000"

    # --- Chat / SSE (architecture.md §3, security.md §4) ---
    chat_max_tool_rounds: int = 4
    chat_hard_timeout_s: int = 90
    chat_max_input_tokens: int = 8000
    chat_history_window_messages: int = 20
    chat_max_message_length: int = 4000
    chat_max_output_tokens: int = 1500

    # --- Generowanie planu (architecture.md §4, ADR-1/2) ---
    plan_reaper_stale_minutes: int = 5
    plan_persona_concurrency_limit: int = 3
    plan_max_output_tokens: int = 4000

    # --- Cennik modeli OpenRouter (ai-pipeline.md §1b, ADR-16) ---
    model_pricing_refresh_seconds: int = 3600
    # Konserwatywne górne oszacowanie USD/token gdy cache cen jest pusty (zimny start) —
    # celowo zawyżone, żeby nie ominąć limitu budżetu przy braku danych z /api/v1/models.
    model_pricing_fallback_usd_per_token: float = 0.00003

    # --- Moderacja (security.md §1, ADR-4) ---
    # Klasyfikator warstwy C wołany zawsze przy trafieniu heurystyki, dodatkowo losowo
    # (obrona w głąb) z tym prawdopodobieństwem nawet bez trafienia.
    moderation_random_sample_rate: float = 0.02

    @property
    def cors_origins_list(self) -> list[str]:
        """Rozbija `CORS_ORIGINS` ("a,b,c") na listę dla CORSMiddleware.allow_origins."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # pola wymagane pochodzą z env/.env


settings = get_settings()
