"""Victim-emotion signal via Hume Expression Measurement (prosody).

This is the acoustic / paralinguistic channel — the thing a text classifier is
structurally blind to. It periodically sends a short rolling window of call
audio to Hume's streaming prosody model and turns the distress-family emotions
into a single `victim_stress` score (0-1) that the risk machine fuses in.

Degraded mode: no HUME_API_KEY → `start()` returns False and the rest of the
app runs exactly as before (warning-only).
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import wave
from collections.abc import Awaitable, Callable

from .config import get_settings

logger = logging.getLogger("sentinel.hume")

# (stress 0-1, {emotion: score} top few) -> None
OnStress = Callable[[float, dict], Awaitable[None]]

INTERVAL = 2.5            # seconds between Hume analyses
WINDOW_SECONDS = 3.0      # analyze the trailing N seconds of audio
SAMPLE_RATE = 16000
BYTES_PER_SEC = SAMPLE_RATE * 2   # 16-bit mono linear16

# Hume emotions that indicate a person under coercion / distress.
STRESS_EMOTIONS = {
    "anxiety", "fear", "distress", "horror", "nervousness", "panic",
    "confusion", "doubt", "sadness", "surprise (negative)", "shame", "awkwardness",
}
# Distress rarely dominates the 48-way distribution, so scale for sensitivity.
STRESS_SCALE = 1.6


def _pcm_to_wav_path(pcm: bytes) -> str:
    f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    f.close()
    with wave.open(f.name, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return f.name


def _stress_from_emotions(emotions) -> tuple[float, dict]:
    matched: dict[str, float] = {}
    total = 0.0
    for e in emotions:
        name = getattr(e, "name", None)
        score = getattr(e, "score", None)
        if name is None and isinstance(e, dict):
            name, score = e.get("name"), e.get("score")
        if name is None or score is None:
            continue
        if name.lower() in STRESS_EMOTIONS:
            total += float(score)
            matched[name] = round(float(score), 3)
    stress = max(0.0, min(1.0, total * STRESS_SCALE))
    top = dict(sorted(matched.items(), key=lambda kv: -kv[1])[:3])
    return stress, top


class HumeProsody:
    """Feeds rolling call audio to Hume and reports a victim-stress score."""

    def __init__(self, on_stress: OnStress) -> None:
        self._on_stress = on_stress
        self._buf = bytearray()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def feed(self, pcm: bytes) -> None:
        self._buf.extend(pcm)
        maxlen = int(WINDOW_SECONDS * BYTES_PER_SEC)
        if len(self._buf) > maxlen:
            del self._buf[: len(self._buf) - maxlen]

    async def start(self) -> bool:
        if not get_settings().has_hume:
            logger.info("Hume key missing — victim-emotion signal off.")
            return False
        self._task = asyncio.create_task(self._loop())
        return True

    async def _loop(self) -> None:
        from hume import AsyncHumeClient
        from hume.expression_measurement.stream import Config

        key = get_settings().hume_api_key
        client = AsyncHumeClient(api_key=key)
        try:
            async with client.expression_measurement.stream.connect(hume_api_key=key) as socket:
                logger.info("Hume prosody stream connected.")
                while not self._stop.is_set():
                    await asyncio.sleep(INTERVAL)
                    if len(self._buf) < BYTES_PER_SEC:  # need ~1s of audio
                        continue
                    path = _pcm_to_wav_path(bytes(self._buf))
                    try:
                        result = await socket.send_file(file_=path, config=Config(prosody={}))
                    finally:
                        try:
                            os.unlink(path)
                        except OSError:
                            pass
                    prosody = getattr(result, "prosody", None)
                    preds = getattr(prosody, "predictions", None) if prosody else None
                    if not preds:
                        continue
                    stress, top = _stress_from_emotions(preds[-1].emotions)
                    await self._on_stress(stress, top)
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # never let Hume hiccups kill the call
            logger.warning("Hume prosody loop error: %s", exc)

    async def close(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
