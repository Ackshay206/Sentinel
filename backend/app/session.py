"""Per-connection session state: the rolling transcript buffer and risk state."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from .config import get_settings
from .risk import RiskState

# How many recent final transcript segments to keep for the classifier window.
MAX_FINALS = 40
# Minimum seconds between classifier calls (debounce — controls cost/latency).
CLASSIFY_INTERVAL = 2.5


@dataclass
class SessionState:
    finals: deque[str] = field(default_factory=lambda: deque(maxlen=MAX_FINALS))
    interim: str = ""
    risk: RiskState = field(default_factory=RiskState)
    last_classify: float = 0.0
    audio_bytes: int = 0

    def __post_init__(self) -> None:
        self.risk.threshold = get_settings().sentinel_risk_threshold

    def add_final(self, text: str) -> None:
        self.finals.append(text)
        self.interim = ""

    def set_interim(self, text: str) -> None:
        self.interim = text

    def window_text(self) -> str:
        """Recent transcript joined into the classifier's input window."""
        return "\n".join(self.finals)

    def due_for_classify(self) -> bool:
        return (time.time() - self.last_classify) >= CLASSIFY_INTERVAL

    def mark_classified(self) -> None:
        self.last_classify = time.time()

    def reset(self) -> None:
        self.finals.clear()
        self.interim = ""
        self.risk.reset()
        self.last_classify = 0.0
        self.audio_bytes = 0
