"""Configuration loaded from environment / .env.

Every external-service key is optional: Sentinel boots and runs the core
pipeline (audio capture, risk state machine, dashboard) even with no keys set.
Each integration exposes a `has_*` flag so the orchestration layer can skip or
stub calls it can't make, instead of crashing.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- API keys (all optional → degraded mode when blank) ---
    deepgram_api_key: str = ""
    openai_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"  # "Sarah" — a calm, clear default voice

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    family_alert_number: str = ""

    # --- Tunables ---
    sentinel_risk_threshold: float = 70.0
    deepgram_model: str = "nova-2"
    openai_model: str = "gpt-4o"  # stronger classifier for recall; override via OPENAI_MODEL
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Capability flags ---
    @property
    def has_deepgram(self) -> bool:
        return bool(self.deepgram_api_key)

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_elevenlabs(self) -> bool:
        return bool(self.elevenlabs_api_key)

    @property
    def has_twilio(self) -> bool:
        return bool(
            self.twilio_account_sid
            and self.twilio_auth_token
            and self.twilio_from_number
            and self.family_alert_number
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def capability_summary(self) -> dict[str, bool]:
        return {
            "deepgram": self.has_deepgram,
            "openai": self.has_openai,
            "elevenlabs": self.has_elevenlabs,
            "twilio": self.has_twilio,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
