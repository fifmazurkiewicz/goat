"""Konfiguracja aplikacji z env — patrz `.env.example` i docs/technical/devops.md sekcja 5."""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"

    database_url: str
    supabase_url: str | None = None
    supabase_jwks_url: str | None = None
    supabase_service_role_key: SecretStr | None = None

    # Lokalny login email/hasło — aktywny wyłącznie przy ENVIRONMENT=local.
    dev_auth_email: str | None = None
    dev_auth_password: SecretStr | None = None
    dev_auth_user_id: str = "00000000-0000-4000-8000-000000000001"
    local_jwt_secret: SecretStr = SecretStr("local-dev-jwt-secret-change-me")

    openrouter_api_key: SecretStr
    # Jeden model domyślnie do czatu i planowania — ustaw Grok (lub inny) w OPENROUTER_CHAT_MODEL.
    # OPENROUTER_PLANNER_MODEL opcjonalny override; pusty = ten sam co chat.
    openrouter_chat_model: str = "x-ai/grok-4-fast"
    openrouter_planner_model: str = ""
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
    chat_llm_title_enabled: bool = True

    # --- Generowanie planu (architecture.md §4, ADR-1/2) ---
    plan_reaper_stale_minutes: int = 5
    plan_persona_concurrency_limit: int = 3
    plan_max_output_tokens: int = 4000
    plan_auto_harmonize_on_upsert: bool = True

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
    def openrouter_plan_model(self) -> str:
        """Model planera — domyślnie identyczny jak czat (jeden model w całej apce)."""
        planner = self.openrouter_planner_model.strip()
        return planner if planner else self.openrouter_chat_model

    @property
    def dev_auth_enabled(self) -> bool:
        return self.environment == "local"

    @property
    def cors_origins_list(self) -> list[str]:
        """Rozbija `CORS_ORIGINS` ("a,b,c") na listę dla CORSMiddleware.allow_origins."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _validate_auth_config(self) -> "Settings":
        if self.dev_auth_enabled:
            if not self.dev_auth_email or self.dev_auth_password is None:
                raise ValueError(
                    "DEV_AUTH_EMAIL i DEV_AUTH_PASSWORD są wymagane przy ENVIRONMENT=local."
                )
        else:
            missing = [
                name
                for name, value in (
                    ("SUPABASE_URL", self.supabase_url),
                    ("SUPABASE_JWKS_URL", self.supabase_jwks_url),
                    ("SUPABASE_SERVICE_ROLE_KEY", self.supabase_service_role_key),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    f"Brak wymaganych zmiennych Supabase w produkcji: {', '.join(missing)}"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # pola wymagane pochodzą z env/.env


settings = get_settings()
