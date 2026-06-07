"""Staged risk-score state machine — the heart of Sentinel.

This is deliberately NOT a keyword filter. It accumulates a 0-100 risk score as
a conversation moves through the social-engineering arc
(authority -> urgency -> secrecy -> payment), and only fires an intervention
when the *trajectory* crosses a threshold, not when a single suspicious word
appears.

Design (all constants are tunable at the top — Phase 5 tunes these against
recorded clips):

  - Each stage has a target risk ceiling. A confident classifier read pulls the
    score smoothly toward that stage's target (legible, climbing meter).
  - Advancing into a higher stage adds a small immediate bump so the meter
    visibly reacts at each escalation.
  - Benign / no-scam reads decay the score, so ordinary chatter drifts back down
    and the meter stays quiet before the scam turns coercive.
  - Firing requires ALL of: score >= threshold, the trajectory has reached
    `secrecy` or `payment`, and at least MIN_CONFIRMATIONS consecutive confident
    scam reads. A lone "gift card" mention early in a friendly call will not fire.

Pure and dependency-free: feed it classification dicts and inspect the result.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .taxonomy import STAGE_RANK, STAGES

# --- Tunables --------------------------------------------------------------
# Risk ceiling each stage pulls the score toward (0-100).
STAGE_TARGET: dict[str, float] = {
    "benign": 0.0,
    "authority": 30.0,
    "urgency": 55.0,
    "secrecy": 78.0,
    "payment": 95.0,
}
# Immediate bump when the conversation first reaches a new, higher stage.
STAGE_ADVANCE_BUMP: float = 8.0
# How fast the score climbs toward a stage target per confident read (0-1).
CLIMB_RATE: float = 0.6
# Multiplicative decay applied on a benign / low-confidence read.
DECAY: float = 0.85
# Minimum classifier confidence for a read to count as scam evidence.
CONFIDENCE_FLOOR: float = 0.45
# Consecutive confident scam reads required before an intervention may fire.
MIN_CONFIRMATIONS: int = 2
# Stages at which firing is permitted (the coercive end of the arc).
FIRING_STAGES: set[str] = {"secrecy", "payment"}
# Above this victim_stress, fire with a single confident read (urgency justifies it).
STRESS_RELAX_THRESHOLD: float = 0.6


@dataclass
class RiskState:
    """Accumulated risk for a single call/session."""

    threshold: float = 70.0
    score: float = 0.0
    current_stage: str = "benign"
    highest_rank: int = 0
    consecutive_confident: int = 0
    scam_type: str = "none"
    red_flags: list[str] = field(default_factory=list)
    fired: bool = False
    victim_stress: float = 0.0
    last_update: float = field(default_factory=time.time)

    # --- core update -------------------------------------------------------
    def update(self, classification: dict, victim_stress: float = 0.0) -> dict:
        """Fold one classifier reading (+ the acoustic victim-stress signal) into risk.

        `classification` is the classifier's structured output:
            {scam_type, stage, confidence, red_flags[], recommended_action}
        `victim_stress` (0-1) is the Hume prosody signal — *how* the victim sounds.

        Returns an event dict describing the new state and whether this update
        is the moment the intervention should fire (`should_fire`).
        """
        self.last_update = time.time()
        self.victim_stress = max(0.0, min(1.0, victim_stress))

        stage = classification.get("stage", "benign")
        if stage not in STAGE_RANK:
            stage = "benign"
        confidence = float(classification.get("confidence", 0.0) or 0.0)
        scam_type = classification.get("scam_type", "none") or "none"
        is_scam_read = (
            scam_type not in ("none", "unknown")
            and stage != "benign"
            and confidence >= CONFIDENCE_FLOOR
        )

        if is_scam_read:
            self.consecutive_confident += 1
            self.scam_type = scam_type

            rank = STAGE_RANK[stage]
            if rank > self.highest_rank:
                # Escalated into a new, higher stage — visible jump + advance.
                self.highest_rank = rank
                self.score = min(100.0, self.score + STAGE_ADVANCE_BUMP)
            self.current_stage = STAGES[self.highest_rank]

            # Climb smoothly toward the (highest-reached) stage's target,
            # scaled by how confident this read is AND by *how the victim sounds*:
            # a stressed victim pushes higher (0.85x calm → 1.15x distressed).
            stress_mod = 0.85 + 0.30 * self.victim_stress
            target = STAGE_TARGET[self.current_stage] * (0.6 + 0.4 * confidence) * stress_mod
            if target > self.score:
                self.score += CLIMB_RATE * (target - self.score)

            # Accumulate unique red flags.
            for flag in classification.get("red_flags", []) or []:
                if flag and flag not in self.red_flags:
                    self.red_flags.append(flag)
        else:
            # Benign / unsure read — relax. Trajectory (highest_rank) is sticky,
            # but the live score and confirmation streak cool off.
            self.consecutive_confident = 0
            self.score *= DECAY
            if self.score < 1.0:
                self.score = 0.0

        self.score = max(0.0, min(100.0, self.score))

        should_fire = self._check_fire()
        if should_fire:
            self.fired = True

        return {
            "type": "risk",
            "score": round(self.score, 1),
            "stage": self.current_stage,
            "highest_rank": self.highest_rank,
            "scam_type": self.scam_type,
            "payment_vector": classification.get("payment_vector", "none"),
            "red_flags": list(self.red_flags),
            "confidence": round(confidence, 2),
            "victim_stress": round(self.victim_stress, 2),
            "fired": self.fired,
            "should_fire": should_fire,
            "recommended_action": classification.get("recommended_action", ""),
        }

    def _check_fire(self) -> bool:
        # A distressed victim justifies firing on a single confident read.
        required = 1 if self.victim_stress >= STRESS_RELAX_THRESHOLD else MIN_CONFIRMATIONS
        return (
            not self.fired
            and self.score >= self.threshold
            and self.current_stage in FIRING_STAGES
            and self.consecutive_confident >= required
        )

    def reset(self) -> None:
        """Re-arm for a new call without reallocating."""
        self.score = 0.0
        self.current_stage = "benign"
        self.highest_rank = 0
        self.consecutive_confident = 0
        self.scam_type = "none"
        self.red_flags = []
        self.fired = False
        self.victim_stress = 0.0
        self.last_update = time.time()

    def snapshot(self) -> dict:
        return {
            "type": "risk",
            "score": round(self.score, 1),
            "stage": self.current_stage,
            "highest_rank": self.highest_rank,
            "scam_type": self.scam_type,
            "red_flags": list(self.red_flags),
            "victim_stress": round(self.victim_stress, 2),
            "fired": self.fired,
            "should_fire": False,
        }
