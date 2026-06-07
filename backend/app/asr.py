"""Streaming ASR via Deepgram's live WebSocket API.

Talks Deepgram's documented wire protocol directly (no SDK) so it's immune to
SDK version churn and works the moment a key is present. Browser PCM frames are
forwarded straight through; transcript segments come back via a callback.

Degraded mode: if no Deepgram key is set, `DeepgramStream.connect()` returns
False and the session runs without live transcription (you can still drive the
classifier/risk pipeline via the manual `/api/inject` test endpoint).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from urllib.parse import urlencode

import websockets

from .config import get_settings

logger = logging.getLogger("sentinel.asr")

OnTranscript = Callable[[str, bool], Awaitable[None]]


async def _connect(url: str, token: str):
    """Open a Deepgram WS, tolerating the websockets header-kwarg rename
    (`extra_headers` < v14, `additional_headers` >= v14)."""
    headers = {"Authorization": f"Token {token}"}
    try:
        return await websockets.connect(url, additional_headers=headers)
    except TypeError:
        return await websockets.connect(url, extra_headers=headers)


class DeepgramStream:
    def __init__(self, on_transcript: OnTranscript) -> None:
        self._on_transcript = on_transcript
        self._ws = None
        self._recv_task: asyncio.Task | None = None
        self._keepalive_task: asyncio.Task | None = None

    async def connect(self) -> bool:
        settings = get_settings()
        if not settings.has_deepgram:
            logger.info("Deepgram key missing — running without live ASR.")
            return False

        params = {
            "model": settings.deepgram_model,
            "encoding": "linear16",
            "sample_rate": "16000",
            "channels": "1",
            "interim_results": "true",
            "punctuate": "true",
            "smart_format": "true",
            "endpointing": "300",
        }
        url = f"wss://api.deepgram.com/v1/listen?{urlencode(params)}"
        try:
            self._ws = await _connect(url, settings.deepgram_api_key)
        except Exception as exc:
            logger.warning("Deepgram connect failed: %s", exc)
            return False

        self._recv_task = asyncio.create_task(self._recv_loop())
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())
        logger.info("Deepgram live stream connected.")
        return True

    async def send(self, pcm: bytes) -> None:
        if self._ws is not None:
            try:
                await self._ws.send(pcm)
            except Exception as exc:
                logger.warning("Deepgram send failed: %s", exc)

    async def _recv_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue
                if msg.get("type") != "Results":
                    continue
                alts = msg.get("channel", {}).get("alternatives", [])
                if not alts:
                    continue
                transcript = (alts[0].get("transcript") or "").strip()
                if not transcript:
                    continue
                is_final = bool(msg.get("is_final"))
                await self._on_transcript(transcript, is_final)
        except websockets.ConnectionClosed:
            logger.info("Deepgram connection closed.")
        except Exception as exc:
            logger.warning("Deepgram recv loop error: %s", exc)

    async def _keepalive_loop(self) -> None:
        """Deepgram drops idle sockets; nudge it during silence."""
        try:
            while self._ws is not None:
                await asyncio.sleep(5)
                try:
                    await self._ws.send(json.dumps({"type": "KeepAlive"}))
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    async def close(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.send(json.dumps({"type": "CloseStream"}))
            except Exception:
                pass
        for task in (self._keepalive_task, self._recv_task):
            if task is not None:
                task.cancel()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
