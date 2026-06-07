"""Intervention: a spoken warning (ElevenLabs) + a family SMS (Twilio).

Fired by the orchestrator when the risk state machine crosses threshold. The
spoken warning is Sentinel's differentiator, so it is built to be *specific*
(derived from the classifier's recommended action), not a generic "this may be a
scam".

Every call degrades gracefully: missing keys -> the step is skipped and reported,
never raised.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from .config import get_settings

logger = logging.getLogger("sentinel.intervention")

_SCAM_LABELS = {
    "grandparent": "a 'grandchild in trouble' scam",
    "bank_impersonation": "someone impersonating your bank",
    "irs_government": "a fake government/IRS scam",
    "government_grant": "a fake government-grant scam",
    "tech_support": "a fake tech-support scam",
    "refund": "a fake refund scam",
    "subscription_renewal": "a fake subscription-renewal scam",
    "delivery_package": "a fake delivery/package scam",
    "loan_debt": "a fake loan / debt-relief scam",
    "investment_crypto": "an investment / crypto scam",
    "pig_butchering": "a romance / crypto investment scam",
    "prize_lottery": "a fake prize/lottery scam",
    "charity": "a fake charity scam",
    "auto_warranty": "an auto-warranty scam",
    "job_employment": "a fake job / work-from-home scam",
    "utility_shutoff": "a fake utility-shutoff scam",
    "unknown": "a likely scam",
    "none": "a likely scam",
}


def build_warning_text(event: dict) -> str:
    """The short, specific line Sentinel speaks into the call."""
    action = (event.get("recommended_action") or "").strip()
    if action:
        return f"Wait — this looks like a scam. {action}"
    label = _SCAM_LABELS.get(event.get("scam_type", "unknown"), "a likely scam")
    return f"Wait — this looks like {label}. Do not send any money or codes. Hang up and check with someone you trust."


def build_sms_text(event: dict) -> str:
    """One-line summary texted to the designated family member."""
    label = _SCAM_LABELS.get(event.get("scam_type", "unknown"), "a likely scam")
    flags = event.get("red_flags") or []
    flag_str = f" Signs: {', '.join(flags[:3])}." if flags else ""
    return (
        f"⚠️ Sentinel alert: the call in progress looks like {label} "
        f"(risk {int(event.get('score', 0))}/100).{flag_str} "
        "Please check on them."
    )


async def synthesize_warning(text: str) -> bytes | None:
    """Render the warning to speech via ElevenLabs. Returns MP3 bytes or None."""
    settings = get_settings()
    if not settings.has_elevenlabs:
        logger.info("ElevenLabs key missing — skipping spoken warning.")
        return None
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "accept": "audio/mpeg",
        "content-type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {"stability": 0.4, "similarity_boost": 0.75},
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                # Surface the actual reason (e.g. paywalled voice, bad model id).
                logger.warning("ElevenLabs TTS failed: %s %s", resp.status_code, resp.text[:300])
                return None
            return resp.content
    except Exception as exc:
        logger.warning("ElevenLabs TTS error: %s", exc)
        return None


async def send_family_sms(text: str) -> bool:
    """Send the family-alert SMS via Twilio. Returns True on success."""
    settings = get_settings()
    if not settings.has_twilio:
        logger.info("Twilio not configured — skipping family SMS.")
        return False

    def _send() -> bool:
        from twilio.rest import Client

        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(
            body=text,
            from_=settings.twilio_from_number,
            to=settings.family_alert_number,
        )
        return True

    try:
        return await asyncio.to_thread(_send)
    except Exception as exc:
        logger.warning("Twilio SMS failed: %s", exc)
        return False
