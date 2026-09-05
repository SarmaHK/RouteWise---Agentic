"""Application configuration for the RouteWise Agentic backend (Workstream A).

Settings are loaded from environment variables (and an optional local ``.env``).
Secrets — notably ``MODEL_STUDIO_API_KEY`` — are read from the environment ONLY and are
never logged or echoed (see docs/DEVELOPMENT_RULES.md → "Environment & secrets").

Phase A1 foundation: only the variables actually needed now are wired. ``DATABASE_URL``
is declared for Workstream B but is intentionally unused during A1.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    environment: str = "development"  # development | production
    log_level: str = "INFO"
    backend_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Alibaba Cloud Model Studio / Qwen (Workstream A) ---
    model_studio_api_key: str = ""  # SECRET — never logged; empty => mock AI client
    model_studio_base_url: str = (
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    )
    model_name: str = "qwen-max"

    # --- Agent loop (Workstream A, A5) ---
    # Upper bound on autonomous tool-calling turns for one request (A5 brief §8). Configurable
    # via env ``MAX_AGENT_ITERATIONS``; a small hackathon-friendly default guarantees the agent
    # loop always terminates (no runaway/infinite tool calling, no background job system).
    max_agent_iterations: int = 8

    # --- Database (Workstream B; declared for future, unused in A1) ---
    database_url: str = ""

    # --- Transit Intelligence & ML (Workstream B) ---
    enable_transit_intelligence: bool = False

    @property
    def cors_origins(self) -> list[str]:
        """CORS origins parsed from the comma-separated env value."""
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]

    @property
    def ai_enabled(self) -> bool:
        """True only when a real Model Studio API key is configured."""
        return bool(self.model_studio_api_key.strip())

    def public_view(self) -> dict[str, object]:
        """A NON-secret snapshot safe for logs/health output. Never includes the key."""
        return {
            "environment": self.environment,
            "model_name": self.model_name,
            "model_studio_base_url": self.model_studio_base_url,
            "ai_enabled": self.ai_enabled,
            "max_agent_iterations": self.max_agent_iterations,
            "database_configured": bool(self.database_url.strip()),
            "transit_intelligence_enabled": self.enable_transit_intelligence,
        }


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Import and call this; do not re-instantiate Settings."""
    return Settings()
