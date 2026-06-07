"""Sentinel backend — FastAPI app + the live session orchestration.

Two paired clients form ONE logical call session over `/ws/session`:
  - role "victim"  (the laptop): its mic → Deepgram (labeled "Victim") AND → Hume
                                 (victim emotion). This client is the DASHBOARD —
                                 all UI events are sent here.
  - role "caller"  (the phone):  its mic → Deepgram (labeled "Caller"); during a
                                 takeover its audio is bridged to the guardian agent.

The classifier runs on the merged, role-labeled transcript window. A client
declares its role with a first `{"type":"join","role":...}` message; a lone
client defaults to "victim" (works solo, with the demo buttons injecting the
caller side).

Control messages (from the victim/dashboard client):
  {"type":"reset"} · {"type":"set_stress","value":0..1}
  {"type":"inject_transcript","text":...} · {"type":"inject_classification","classification":{...}}
"""

from __future__ import annotations

import base64
import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .asr import DeepgramStream
from .classifier import classify
from .config import get_settings
from .hume import HumeProsody
from .intervention import (
    build_sms_text,
    build_warning_text,
    send_family_alert,
    synthesize_warning,
)
from .session import SessionState
from .takeover import TakeoverSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("sentinel")

settings = get_settings()
app = FastAPI(title="Sentinel", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "capabilities": settings.capability_summary(),
        "risk_threshold": settings.sentinel_risk_threshold,
    }


class Room:
    """One call session shared by a victim (dashboard) and an optional caller client."""

    def __init__(self) -> None:
        self.state = SessionState()
        self.dashboard: WebSocket | None = None      # the victim/laptop client
        self.hume = HumeProsody(self._on_stress)
        self.takeover: dict = {"session": None}
        self.victim_asr: DeepgramStream | None = None
        self.caller_asr: DeepgramStream | None = None
        # For the single-mic "role toggle" demo: which role the current mic input is.
        self.input_role: str = "victim"

    # --- outbound UI (always to the dashboard) ---
    async def send(self, obj: dict) -> None:
        ws = self.dashboard
        if ws is None:
            return
        try:
            await ws.send_json(obj)
        except Exception:
            pass

    async def _on_stress(self, stress: float, top: dict) -> None:
        self.state.victim_stress = stress
        await self.send({"type": "emotion", "stress": round(stress, 2), "emotions": top})

    async def on_agent_audio(self, b64: str, sample_rate: int) -> None:
        await self.send({"type": "agent_audio", "audio_b64": b64, "sample_rate": sample_rate})

    async def on_agent_message(self, role: str, text: str) -> None:
        await self.send({"type": "takeover_msg", "role": role, "text": text})

    async def start_takeover(self, event: dict) -> bool:
        ts = TakeoverSession(self.on_agent_audio, self.on_agent_message)
        flags = ", ".join(event.get("red_flags", [])) or "suspicious demands for payment or personal information"
        context = (
            f"You have taken over a suspected '{event.get('scam_type')}' scam. "
            f"The specific red flags observed so far are: {flags}. "
            "Challenge these specific tactics first — ask why the caller needs them and say no "
            "legitimate organization does this — then demand the caller identify themselves."
        )
        ok = await ts.start(context)
        if ok:
            self.takeover["session"] = ts
        return ok

    def make_on_transcript(self, label: str, speaker: int):
        async def cb(text: str, is_final: bool, _spk: int | None = None) -> None:
            if is_final:
                self.state.add_final(text, label)
                await self.send({"type": "transcript", "text": text, "is_final": True, "speaker": speaker, "label": label})
                # During takeover the call is agent↔caller — don't re-run the classifier.
                if self.state.mode != "takeover" and self.state.due_for_classify():
                    await _run_pipeline(self)
            else:
                self.state.set_interim(text)
                await self.send({"type": "transcript", "text": text, "is_final": False, "speaker": speaker, "label": label})
        return cb

    async def close(self) -> None:
        for a in (self.victim_asr, self.caller_asr):
            if a is not None:
                await a.close()
        await self.hume.close()
        if self.takeover["session"] is not None:
            await self.takeover["session"].close()


# Single live session (demo-grade: one paired call at a time).
LIVE: Room | None = None


async def _run_pipeline(room: Room) -> None:
    window = room.state.window_text()
    if not window.strip():
        return
    room.state.mark_classified()
    classification = await classify(window)
    if classification is None:
        return
    await _apply_classification(classification, room)


async def _apply_classification(classification: dict, room: Room) -> None:
    event = room.state.risk.update(classification, victim_stress=room.state.victim_stress)
    event["mode"] = room.state.mode
    await room.send(event)
    if event.get("should_fire"):
        await _fire_intervention(event, room)


async def _fire_intervention(event: dict, room: Room) -> None:
    """Emotion-gated: calm victim → spoken warning; stressed victim → take over the call."""
    s = get_settings()
    stressed = float(event.get("victim_stress", 0.0)) >= s.stress_takeover_threshold

    if s.takeover_enabled and stressed and s.has_elevenlabs:
        room.state.mode = "takeover"
        logger.info("INTERVENTION → TAKEOVER (stress=%.2f, score=%s)", event.get("victim_stress", 0), event.get("score"))
        await room.send({"type": "mode", "mode": "takeover", "reason": "victim distress"})
        await room.send({
            "type": "intervention",
            "warning_text": "Sentinel is taking over the call to protect you.",
            "sms_text": build_sms_text(event),
            "scam_type": event.get("scam_type"),
            "score": event.get("score"),
            "red_flags": event.get("red_flags", []),
        })
        started = await room.start_takeover(event)
        if started:
            # The call is now agent↔caller: tag the mic as Caller so ONLY the
            # caller's audio reaches the agent, and it waits for the caller to reply.
            room.input_role = "caller"
            await room.send({"type": "input_role", "role": "caller"})
        else:  # ConvAI unavailable → fall back to a spoken warning
            room.state.mode = "warning"
            await room.send({"type": "mode", "mode": "warning"})
            await _warn(event, room)
        await _alert_family(build_sms_text(event), "Sentinel is handling a scam call for your family member.", room)
    else:
        room.state.mode = "warning"
        await room.send({"type": "mode", "mode": "warning"})
        await _warn(event, room)
        await _alert_family(build_sms_text(event), build_warning_text(event), room)


async def _warn(event: dict, room: Room) -> None:
    warning_text = build_warning_text(event)
    logger.info("INTERVENTION fired (warning): %s", warning_text)
    await room.send({
        "type": "intervention",
        "warning_text": warning_text,
        "sms_text": build_sms_text(event),
        "scam_type": event.get("scam_type"),
        "score": event.get("score"),
        "red_flags": event.get("red_flags", []),
    })
    audio = await synthesize_warning(warning_text)
    if audio:
        await room.send({
            "type": "tts", "mime": "audio/mpeg", "text": warning_text,
            "audio_b64": base64.b64encode(audio).decode("ascii"),
        })


async def _alert_family(summary: str, spoken: str, room: Room) -> None:
    results = await send_family_alert(summary, spoken)
    ok_channels = [r["channel"] for r in results if r.get("ok")]
    sent = bool(ok_channels)
    if sent:
        text = f"Family alerted via {', '.join(ok_channels)}"
    elif results:
        text = "Alert failed: " + "; ".join(f"{r['channel']}: {r.get('reason')}" for r in results)
    else:
        text = "No alert channel configured"
    await room.send({"type": "sms", "sent": sent, "text": text})


def _parse_join_role(first_text: str | None) -> str:
    if first_text:
        try:
            m = json.loads(first_text)
            if m.get("type") == "join":
                return "caller" if m.get("role") == "caller" else "victim"
        except json.JSONDecodeError:
            pass
    return "victim"


@app.websocket("/ws/session")
async def session_socket(ws: WebSocket) -> None:
    global LIVE
    await ws.accept()

    # First message declares the role (victim=dashboard, caller=phone).
    try:
        first = await ws.receive()
    except WebSocketDisconnect:
        return
    if first.get("type") == "websocket.disconnect":
        return
    role = _parse_join_role(first.get("text"))

    if role == "caller":
        await _run_caller(ws, first)
    else:
        await _run_victim(ws, first)


async def _run_caller(ws: WebSocket, first: dict) -> None:
    """The phone: its mic is transcribed as 'Caller' and (during takeover) bridged to the agent."""
    global LIVE
    room = LIVE if LIVE is not None else Room()
    LIVE = room
    room.caller_asr = DeepgramStream(room.make_on_transcript("Caller", 1))
    await room.caller_asr.connect()
    await ws.send_json({"type": "caller_ready"})
    logger.info("caller client joined")

    async def handle(data: bytes) -> None:
        if room.caller_asr is not None:
            await room.caller_asr.send(data)
        ts = room.takeover["session"]
        if ts is not None:
            await ts.feed(data)  # bridge the scammer's audio to the guardian agent

    try:
        if (b := first.get("bytes")) is not None:
            await handle(b)
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if (data := msg.get("bytes")) is not None:
                await handle(data)
    except WebSocketDisconnect:
        pass
    finally:
        if room.caller_asr is not None:
            await room.caller_asr.close()
            room.caller_asr = None
        logger.info("caller client left")


async def _run_victim(ws: WebSocket, first: dict) -> None:
    """The laptop: dashboard + victim mic (→ Deepgram 'Victim' and → Hume)."""
    global LIVE
    # Reuse a caller-created room that has no dashboard yet; else start fresh.
    room = LIVE if (LIVE is not None and LIVE.dashboard is None) else Room()
    LIVE = room
    room.dashboard = ws

    await ws.send_json({"type": "ready", "capabilities": settings.capability_summary()})
    # Both ASR streams exist so the single mic can be tagged Victim or Caller
    # via the role toggle (and so a separate caller device can also attach).
    room.victim_asr = DeepgramStream(room.make_on_transcript("Victim", 0))
    if room.caller_asr is None:
        room.caller_asr = DeepgramStream(room.make_on_transcript("Caller", 1))
        await room.caller_asr.connect()
    await room.victim_asr.connect()
    await room.hume.start()
    logger.info("victim/dashboard joined (capabilities=%s)", settings.capability_summary())

    async def handle_audio(data: bytes) -> None:
        if room.state.audio_bytes == 0:
            logger.info("receiving mic audio (capture OK)")
        room.state.audio_bytes += len(data)
        if room.input_role == "caller":
            # Mic is currently voicing the scammer → Caller transcript + (during
            # takeover) bridge to the guardian agent. NOT sent to Hume.
            if room.caller_asr is not None:
                await room.caller_asr.send(data)
            ts = room.takeover["session"]
            if ts is not None:
                await ts.feed(data)
        else:
            if room.victim_asr is not None:
                await room.victim_asr.send(data)   # victim transcript
            room.hume.feed(data)                   # victim emotion ONLY

    try:
        if (b := first.get("bytes")) is not None:
            await handle_audio(b)
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if (data := msg.get("bytes")) is not None:
                await handle_audio(data)
            elif (text := msg.get("text")) is not None:
                await _handle_control(text, room)
    except WebSocketDisconnect:
        pass
    finally:
        await room.close()
        if LIVE is room:
            LIVE = None
        logger.info("victim/dashboard left (%d audio bytes)", room.state.audio_bytes)


async def _handle_control(text: str, room: Room) -> None:
    try:
        msg = json.loads(text)
    except json.JSONDecodeError:
        return
    kind = msg.get("type")

    if kind == "join":
        return  # already handled at connect
    if kind == "reset":
        room.state.reset()
        if room.takeover["session"] is not None:
            await room.takeover["session"].close()
            room.takeover["session"] = None
        await room.send({"type": "reset_ok"})
        await room.send({"type": "mode", "mode": "monitoring"})
        await room.send(room.state.risk.snapshot())
    elif kind == "set_role":
        # Single-mic role toggle: tag the current mic input as victim or caller.
        room.input_role = "caller" if msg.get("role") == "caller" else "victim"
        await room.send({"type": "input_role", "role": room.input_role})
    elif kind == "set_stress":
        try:
            room.state.victim_stress = max(0.0, min(1.0, float(msg.get("value", 0.0))))
        except (TypeError, ValueError):
            return
        await room.send({"type": "emotion", "stress": round(room.state.victim_stress, 2), "emotions": {}})
    elif kind == "inject_transcript":
        line = (msg.get("text") or "").strip()
        if line:
            room.state.add_final(line, "Caller")
            await room.send({"type": "transcript", "text": line, "is_final": True, "speaker": 1, "label": "Caller"})
            await _run_pipeline(room)
    elif kind == "inject_classification":
        # Demo/offline: injected lines are the scammer ("Caller").
        line = (msg.get("line") or "").strip()
        if line:
            room.state.add_final(line, "Caller")
            await room.send({"type": "transcript", "text": line, "is_final": True, "speaker": 1, "label": "Caller"})
        classification = msg.get("classification") or {}
        await _apply_classification(classification, room)
