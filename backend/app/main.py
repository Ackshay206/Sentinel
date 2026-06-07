"""Sentinel backend — FastAPI app + the live session orchestration.

The single websocket `/ws/session` carries the whole loop:

  browser  --(binary PCM frames)-->  Deepgram ASR  -->  transcript
  browser  <--(JSON: transcript / risk / intervention / tts)--  backend

Control messages (JSON text frames from the browser) let you drive the pipeline
without a microphone — useful for testing and demos:
  {"type": "reset"}
  {"type": "inject_transcript", "text": "..."}        # needs OpenAI key
  {"type": "inject_classification", "classification": {...}}  # no keys needed
"""

from __future__ import annotations

import base64
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .asr import DeepgramStream
from .classifier import classify
from .config import get_settings
from .intervention import (
    build_sms_text,
    build_warning_text,
    send_family_sms,
    synthesize_warning,
)
from .session import SessionState

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("sentinel")

settings = get_settings()
app = FastAPI(title="Sentinel", version="0.1.0")

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


async def _run_pipeline(session: SessionState, ws: WebSocket) -> None:
    """Classify the current transcript window and fold it into risk."""
    window = session.window_text()
    if not window.strip():
        return
    session.mark_classified()
    classification = await classify(window)
    if classification is None:
        return
    await _apply_classification(classification, session, ws)


async def _apply_classification(classification: dict, session: SessionState, ws: WebSocket) -> None:
    event = session.risk.update(classification)
    await ws.send_json(event)
    if event.get("should_fire"):
        await _fire_intervention(event, ws)


async def _fire_intervention(event: dict, ws: WebSocket) -> None:
    warning_text = build_warning_text(event)
    sms_text = build_sms_text(event)
    logger.info("INTERVENTION fired: %s", warning_text)

    # Tell the dashboard immediately so the UI reacts without waiting on TTS/SMS.
    await ws.send_json(
        {
            "type": "intervention",
            "warning_text": warning_text,
            "sms_text": sms_text,
            "scam_type": event.get("scam_type"),
            "score": event.get("score"),
            "red_flags": event.get("red_flags", []),
        }
    )

    # Spoken warning into the victim's ear (browser auto-plays the audio).
    audio = await synthesize_warning(warning_text)
    if audio:
        await ws.send_json(
            {
                "type": "tts",
                "mime": "audio/mpeg",
                "text": warning_text,
                "audio_b64": base64.b64encode(audio).decode("ascii"),
            }
        )

    # Family alert.
    sent = await send_family_sms(sms_text)
    await ws.send_json({"type": "sms", "sent": sent, "text": sms_text})


@app.websocket("/ws/session")
async def session_socket(ws: WebSocket) -> None:
    await ws.accept()
    session = SessionState()
    logger.info("session connected (capabilities=%s)", settings.capability_summary())

    await ws.send_json({"type": "ready", "capabilities": settings.capability_summary()})

    async def on_transcript(text: str, is_final: bool) -> None:
        if is_final:
            session.add_final(text)
            await ws.send_json({"type": "transcript", "text": text, "is_final": True})
            if session.due_for_classify():
                await _run_pipeline(session, ws)
        else:
            session.set_interim(text)
            await ws.send_json({"type": "transcript", "text": text, "is_final": False})

    asr = DeepgramStream(on_transcript)
    await asr.connect()

    try:
        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                break

            if (data := message.get("bytes")) is not None:
                if session.audio_bytes == 0:
                    logger.info("receiving mic audio from browser (capture OK)")
                session.audio_bytes += len(data)
                await asr.send(data)
            elif (text := message.get("text")) is not None:
                await _handle_control(text, session, ws)
    except WebSocketDisconnect:
        pass
    finally:
        await asr.close()
        logger.info("session closed (%d audio bytes)", session.audio_bytes)


async def _handle_control(text: str, session: SessionState, ws: WebSocket) -> None:
    import json

    try:
        msg = json.loads(text)
    except json.JSONDecodeError:
        return
    kind = msg.get("type")

    if kind == "reset":
        session.reset()
        await ws.send_json({"type": "reset_ok"})
        await ws.send_json(session.risk.snapshot())
    elif kind == "inject_transcript":
        # Treat typed text as a final transcript segment (drives the classifier).
        line = (msg.get("text") or "").strip()
        if line:
            session.add_final(line)
            await ws.send_json({"type": "transcript", "text": line, "is_final": True})
            await _run_pipeline(session, ws)
    elif kind == "inject_classification":
        # Feed the risk machine directly — works with zero API keys (demo/offline).
        # Optional `line` is echoed as a transcript segment so the demo also
        # populates the transcript panel without Deepgram.
        line = (msg.get("line") or "").strip()
        if line:
            session.add_final(line)
            await ws.send_json({"type": "transcript", "text": line, "is_final": True})
        classification = msg.get("classification") or {}
        await _apply_classification(classification, session, ws)
