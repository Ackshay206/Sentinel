"""Configuration loaded from environment / .env.

Every external-service key is optional: Sentinel boots and runs the core
pipeline (audio capture, risk state machine, dashboard) even with no keys set.
Each integration exposes a `has_*` flag so the orchestration layer can skip or
stub calls it can't make, instead of crashing.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute path to backend/.env so config loads regardless of the launch CWD.
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH), env_file_encoding="utf-8", extra="ignore"
    )

    # --- API keys (all optional → degraded mode when blank) ---
    deepgram_api_key: str = ""
    openai_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"  # "Sarah" — a calm, clear default voice

    # Hume Expression Measurement (prosody) — victim emotion signal.
    hume_api_key: str = ""

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""        # SMS-capable Twilio number (sms channel)
    family_alert_number: str = ""       # SMS + voice-call destination

    # Alert channels: comma-separated subset of {sms, whatsapp, call}.
    twilio_alert_channels: str = "sms"
    # WhatsApp (Twilio sandbox by default — recipient must `join` it first).
    twilio_whatsapp_from: str = "whatsapp:+14155238886"
    family_whatsapp_number: str = ""    # e.g. +919962496372 (whatsapp channel destination)
    # Voice-capable Twilio number for the 'call' channel (falls back to from_number).
    twilio_voice_from: str = ""

    # --- Tunables ---
    sentinel_risk_threshold: float = 70.0
    deepgram_model: str = "nova-2"
    deepgram_diarize: bool = True       # separate victim vs scammer speakers
    openai_model: str = "gpt-4o"  # stronger classifier for recall; override via OPENAI_MODEL
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Voice-agent: emotion-gated takeover ---
    # When a scam fires AND victim_stress >= this, Sentinel takes over the call
    # (ElevenLabs ConvAI) instead of only speaking a warning.
    takeover_enabled: bool = True
    stress_takeover_threshold: float = 0.55
    # Reuse a pre-created ConvAI agent if set; otherwise one is created on demand.
    takeover_agent_id: str = ""

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
    def has_hume(self) -> bool:
        return bool(self.hume_api_key)

    @property
    def alert_channels(self) -> list[str]:
        return [c.strip().lower() for c in self.twilio_alert_channels.split(",") if c.strip()]

    @property
    def voice_from(self) -> str:
        return self.twilio_voice_from or self.twilio_from_number

    def channel_ready(self, channel: str) -> bool:
        """Is this alert channel fully configured?"""
        if not (self.twilio_account_sid and self.twilio_auth_token):
            return False
        if channel == "sms":
            return bool(self.twilio_from_number and self.family_alert_number)
        if channel == "whatsapp":
            return bool(self.twilio_whatsapp_from and self.family_whatsapp_number)
        if channel == "call":
            return bool(self.voice_from and self.family_alert_number)
        return False

    @property
    def has_twilio(self) -> bool:
        # The "alerting" capability is ready if any configured channel can send.
        return any(self.channel_ready(c) for c in self.alert_channels)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def capability_summary(self) -> dict[str, bool]:
        return {
            "deepgram": self.has_deepgram,
            "openai": self.has_openai,
            "elevenlabs": self.has_elevenlabs,
            "twilio": self.has_twilio,
            "hume": self.has_hume,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
