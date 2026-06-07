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


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _twilio_client():
    from twilio.rest import Client

    s = get_settings()
    return Client(s.twilio_account_sid, s.twilio_auth_token)


def _send_message(from_: str, to: str, body: str) -> str:
    msg = _twilio_client().messages.create(body=body, from_=from_, to=to)
    return msg.sid


def _place_call(from_: str, to: str, spoken: str) -> str:
    # Twilio reads the warning aloud via the <Say> verb (built-in TTS).
    twiml = f"<Response><Say voice=\"Polly.Joanna\">{_xml_escape(spoken)}</Say></Response>"
    call = _twilio_client().calls.create(from_=from_, to=to, twiml=twiml)
    return call.sid


async def send_family_alert(summary: str, spoken: str) -> list[dict]:
    """Send the family alert across every configured channel (sms / whatsapp / call).

    `summary` is the one-line text (SMS/WhatsApp); `spoken` is the warning the
    phone-call reads aloud. Returns a per-channel result list — never raises.
    """
    settings = get_settings()
    results: list[dict] = []
    for ch in settings.alert_channels:
        if not settings.channel_ready(ch):
            logger.info("alert channel '%s' not configured — skipping.", ch)
            results.append({"channel": ch, "ok": False, "reason": "not configured"})
            continue
        try:
            if ch == "sms":
                sid = await asyncio.to_thread(
                    _send_message, settings.twilio_from_number, settings.family_alert_number, summary
                )
            elif ch == "whatsapp":
                sid = await asyncio.to_thread(
                    _send_message,
                    settings.twilio_whatsapp_from,
                    f"whatsapp:{settings.family_whatsapp_number}",
                    summary,
                )
            elif ch == "call":
                sid = await asyncio.to_thread(
                    _place_call, settings.voice_from, settings.family_alert_number, spoken
                )
            else:
                results.append({"channel": ch, "ok": False, "reason": "unknown channel"})
                continue
            logger.info("alert sent via %s (sid=%s)", ch, sid)
            results.append({"channel": ch, "ok": True, "sid": sid})
        except Exception as exc:
            logger.warning("alert via %s failed: %s", ch, exc)
            results.append({"channel": ch, "ok": False, "reason": str(exc)[:160]})
    return results
