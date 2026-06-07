"""Scam classifier — OpenAI GPT-4o-mini with structured JSON output.

Given a rolling transcript window, returns a structured assessment of where the
conversation currently sits in the social-engineering arc. The risk state
machine (`risk.py`) consumes these readings; this module makes no firing
decisions itself.

Degraded mode: if no OpenAI key is configured, `classify()` returns None and the
pipeline simply doesn't advance risk (the rest of the app still runs).
"""

from __future__ import annotations

import json
import logging

from .config import get_settings
from .taxonomy import PAYMENT_VECTORS, SCAM_TYPES, STAGES, build_taxonomy_brief

logger = logging.getLogger("sentinel.classifier")

_SYSTEM_PROMPT = f"""You are Sentinel, a real-time scam-call analyst protecting a vulnerable person \
(often elderly) who is ON a phone call right now. You receive a rolling transcript of the live call \
and must judge where the conversation currently sits in the social-engineering arc.

{build_taxonomy_brief()}

Think first, then decide. In `reasoning`, briefly (1-3 sentences) note which manipulation tactics \
appear in the transcript and how far the conversation has escalated. THEN fill in the verdict fields.

How to assess:
- `reasoning`: your short rationale — what tactics you see and the escalation so far. Reason about the WHOLE conversation, not just the last line.
- `stage`: the MOST ADVANCED stage clearly reached so far (benign, authority, urgency, secrecy, payment). Stages are sticky — once urgency or secrecy has appeared, a later calm line does not reset it.
- `scam_type`: best-matching PRETEXT pattern; "none" for ordinary conversation, "unknown" if it smells like a scam but fits no listed pattern.
- `payment_vector`: the irreversible ASK currently being pushed — gift_card, wire_transfer, crypto_wallet, bank_or_card_details, otp_code, upfront_fee, remote_access, or courier_cash. Use "none" if no such ask has been made yet. This is independent of the pretext: many different scams end in the same ask. When any vector other than "none" is being pushed, `stage` is almost always "payment".
- `confidence` (0.0-1.0): how confident you are that this is a scam in progress. It should ACCUMULATE — the more manipulation tactics and the further the escalation, the higher it goes (a clear payment-coercion push should be ~0.9+). Ordinary friendly conversation stays low (<0.2).
- Recognize PARAPHRASES, not just exact phrases. Real scammers improvise; match the intent (impersonating authority, scaring, isolating, extracting payment/codes), not literal keywords.
- FACT-CHECK claimed authorities against what you know. Scammers invent official-sounding agencies, departments, and bureaus that do not exist (e.g. a "US Grants Department", "Federal Grants Administration", "National Grants Bureau", "Account Protection Bureau"). If a caller claims to represent an official body that does not plausibly exist as a real entity — or a real body acting in a way it never would (cold-calling to offer "free government grants", demanding gift cards, asking for codes) — treat that as a strong scam signal. In particular, the U.S. government does not cold-call people to award grants; legitimate federal grants are applied for at grants.gov. When you flag a suspicious or non-existent entity, name it in `reasoning` and in `red_flags` (e.g. "claims to be from a non-existent 'US Grants Department'").
- Judge the TRAJECTORY. A lone mention of "gift card" in a warm family chat is not a scam; escalating pressure (authority -> urgency -> secrecy -> irreversible payment) is. But do not be timid: if the escalation is clearly underway, say so with appropriate confidence. Missing a real scam is worse than a mild over-estimate, as long as ordinary conversation still scores low.
- `red_flags`: short phrases naming the specific tactics observed (e.g. "claims to be the IRS", "threatens arrest", "asks to keep it secret", "wants gift-card codes"). Empty if benign.
- `recommended_action`: ONE short, SPECIFIC spoken instruction to the victim IF this is a scam — concrete, not generic. Good: "Do not read them the gift card numbers." / "Hang up and call your bank using the number on your card." Bad: "This may be a scam." Empty string if benign."""

_RESPONSE_SCHEMA = {
    "name": "scam_assessment",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "reasoning": {"type": "string"},
            "scam_type": {"type": "string", "enum": SCAM_TYPES},
            "payment_vector": {"type": "string", "enum": PAYMENT_VECTORS},
            "stage": {"type": "string", "enum": STAGES},
            "confidence": {"type": "number"},
            "red_flags": {"type": "array", "items": {"type": "string"}},
            "recommended_action": {"type": "string"},
        },
        "required": ["reasoning", "scam_type", "payment_vector", "stage", "confidence", "red_flags", "recommended_action"],
    },
}

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import AsyncOpenAI

        # max_retries lets the SDK ride out 429s (low-tier TPM limits) with backoff.
        _client = AsyncOpenAI(api_key=get_settings().openai_api_key, max_retries=5)
    return _client


async def classify(transcript_window: str) -> dict | None:
    """Assess the current scam state of the transcript window.

    Returns the structured assessment dict, or None if classification is
    unavailable (no key) or failed.
    """
    settings = get_settings()
    if not settings.has_openai:
        return None
    if not transcript_window.strip():
        return None

    try:
        client = _get_client()
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            temperature=0,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Live call transcript so far (most recent last):\n\n"
                        f"{transcript_window}\n\n"
                        "Assess the current state."
                    ),
                },
            ],
            response_format={"type": "json_schema", "json_schema": _RESPONSE_SCHEMA},
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        # Clamp confidence defensively.
        data["confidence"] = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
        logger.info(
            "classify[%s] → scam=%s vector=%s stage=%s conf=%.2f flags=%s | %s",
            settings.openai_model,
            data.get("scam_type"),
            data.get("payment_vector"),
            data.get("stage"),
            data["confidence"],
            data.get("red_flags"),
            (data.get("reasoning") or "")[:160],
        )
        return data
    except Exception as exc:  # hackathon: never let a classifier hiccup kill the call
        logger.warning("classifier error: %s", exc)
        return None
