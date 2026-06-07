"""Call takeover via ElevenLabs Conversational AI (Agents).

When a scam fires AND the victim sounds distressed, Sentinel stops merely
warning and *takes over the call*: it bridges the live audio to an ElevenLabs
ConvAI "guardian" agent that talks to the scammer — refusing codes/payments,
demanding the caller identify themselves, and stating the call is monitored.
ConvAI handles STT + LLM + TTS + turn-taking + interruption natively.

Degraded mode: no ElevenLabs key / agent creation fails → `start()` returns
False and the orchestrator falls back to the spoken warning.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from collections.abc import Awaitable, Callable

import httpx
import websockets

from .config import get_settings

logger = logging.getLogger("sentinel.takeover")

GUARDIAN_PROMPT = (
    "You are Sentinel, a fraud-protection voice agent. You have detected a scam in progress "
    "against a vulnerable person and have TAKEN OVER the phone call to protect them. You are now "
    "speaking directly to the suspected scammer.\n"
    "Work in this ORDER:\n"
    "1) CHALLENGE THE RED FLAGS FIRST. Open by calling out the specific manipulation tactics the "
    "caller is using — demands for gift cards, wire transfers, or crypto; requests for remote access "
    "to a computer; demands for one-time codes/OTPs, card numbers, or bank details; threats; "
    "manufactured urgency; or demands for secrecy. Ask pointed questions about each: 'Why would you "
    "need that?' and make clear that no legitimate bank, company, or government agency ever asks for "
    "those things.\n"
    "2) THEN DEMAND THEIR IDENTITY. Once you've challenged the tactics, press the caller to identify "
    "themselves: full name, the company they represent, their employee or badge number, an official "
    "callback number, and a case or reference number.\n"
    "THROUGHOUT: PROTECT — never reveal any personal information, codes, OTPs, card or bank details, "
    "and state plainly that no money, gift cards, or codes will be sent. Note that this call is being "
    "monitored and recorded for fraud protection.\n"
    "Be calm, firm, and brief — one or two sentences per turn. Never threaten. If the caller hangs "
    "up, you have succeeded."
)
FIRST_MESSAGE = (
    "Hello — this is Sentinel, a fraud-protection line, and I'm handling this call now. "
    "Before anything else: I have serious concerns about what you're asking for. "
    "Why exactly do you need that from this person?"
)

OnAgentAudio = Callable[[str, int], Awaitable[None]]   # (base64_pcm, sample_rate)
OnMessage = Callable[[str, str], Awaitable[None]]      # (role: 'agent'|'caller', text)

_agent_id_cache: str | None = None


async def _connect(url: str, key: str):
    headers = {"xi-api-key": key}
    try:
        return await websockets.connect(url, additional_headers=headers, max_size=16 * 1024 * 1024)
    except TypeError:
        return await websockets.connect(url, extra_headers=headers, max_size=16 * 1024 * 1024)


async def ensure_agent() -> str | None:
    """Create (once) or reuse the ConvAI guardian agent; return its id."""
    global _agent_id_cache
    s = get_settings()
    if not s.has_elevenlabs:
        return None
    if s.takeover_agent_id:
        return s.takeover_agent_id
    if _agent_id_cache:
        return _agent_id_cache

    body = {
        "name": "Sentinel Guardian",
        "conversation_config": {
            "agent": {
                "prompt": {"prompt": GUARDIAN_PROMPT, "llm": "gpt-4o-mini"},
                "first_message": FIRST_MESSAGE,
                "language": "en",
            },
            "tts": {"voice_id": s.elevenlabs_voice_id},
        },
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.post(
                "https://api.elevenlabs.io/v1/convai/agents/create",
                headers={"xi-api-key": s.elevenlabs_api_key},
                json=body,
            )
            if r.status_code != 200:
                logger.warning("ConvAI agent create failed: %s %s", r.status_code, r.text[:300])
                return None
            _agent_id_cache = r.json().get("agent_id")
            logger.info("created ConvAI guardian agent %s", _agent_id_cache)
            return _agent_id_cache
    except Exception as exc:
        logger.warning("ConvAI agent create error: %s", exc)
        return None


class TakeoverSession:
    """Bridges live call audio to an ElevenLabs ConvAI guardian agent."""

    def __init__(self, on_agent_audio: OnAgentAudio, on_message: OnMessage) -> None:
        self._on_audio = on_agent_audio
        self._on_message = on_message
        self._ws = None
        self._recv_task: asyncio.Task | None = None
        self._sample_rate = 16000  # updated from conversation_initiation_metadata

    async def start(self, context: str | None = None) -> bool:
        agent_id = await ensure_agent()
        if not agent_id:
            return False
        url = f"wss://api.elevenlabs.io/v1/convai/conversation?agent_id={agent_id}"
        try:
            self._ws = await _connect(url, get_settings().elevenlabs_api_key)
        except Exception as exc:
            logger.warning("ConvAI connect failed: %s", exc)
            return False
        await self._ws.send(json.dumps({"type": "conversation_initiation_client_data"}))
        # Feed the agent the *specific* detected red flags so it challenges those
        # first (non-interrupting contextual update).
        if context:
            await self._ws.send(json.dumps({"type": "contextual_update", "text": context}))
        self._recv_task = asyncio.create_task(self._recv_loop())
        logger.info("takeover: ConvAI guardian connected.")
        return True

    async def feed(self, pcm: bytes) -> None:
        """Forward the scammer's audio (16 kHz linear16 PCM) to the agent."""
        if self._ws is None:
            return
        try:
            await self._ws.send(json.dumps({"user_audio_chunk": base64.b64encode(pcm).decode("ascii")}))
        except Exception:
            pass

    async def _recv_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                try:
                    data = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue
                t = data.get("type")
                if t == "ping":
                    await self._ws.send(
                        json.dumps({"type": "pong", "event_id": data.get("ping_event", {}).get("event_id")})
                    )
                elif t == "audio":
                    b64 = data.get("audio_event", {}).get("audio_base_64")
                    if b64:
                        await self._on_audio(b64, self._sample_rate)
                elif t == "agent_response":
                    txt = data.get("agent_response_event", {}).get("agent_response", "")
                    if txt:
                        await self._on_message("agent", txt)
                elif t == "user_transcript":
                    txt = data.get("user_transcription_event", {}).get("user_transcript", "")
                    if txt:
                        await self._on_message("caller", txt)
                elif t == "conversation_initiation_metadata":
                    meta = data.get("conversation_initiation_metadata_event", {})
                    fmt = meta.get("agent_output_audio_format", "pcm_16000")
                    if isinstance(fmt, str) and "pcm_" in fmt:
                        try:
                            self._sample_rate = int(fmt.split("_")[-1])
                        except ValueError:
                            pass
        except websockets.ConnectionClosed:
            logger.info("takeover: ConvAI connection closed.")
        except Exception as exc:
            logger.warning("takeover recv error: %s", exc)

    async def close(self) -> None:
        if self._recv_task is not None:
            self._recv_task.cancel()
            self._recv_task = None
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
