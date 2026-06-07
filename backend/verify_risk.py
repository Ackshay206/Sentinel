"""Offline verification of the staged risk state machine (no API keys needed).

Run from the backend dir:   python verify_risk.py

Asserts the behavior that separates Sentinel from a keyword filter:
  - ordinary conversation stays calm,
  - a lone scary keyword early does NOT fire,
  - a full escalating trajectory DOES fire at the coercive end,
  - benign talk after a scare decays the score back down.
"""

from __future__ import annotations

from app.risk import RiskState


def reading(scam_type, stage, confidence, red_flags=None, action=""):
    return {
        "scam_type": scam_type,
        "stage": stage,
        "confidence": confidence,
        "red_flags": red_flags or [],
        "recommended_action": action,
    }


def feed(state: RiskState, readings: list[dict]) -> list[dict]:
    return [state.update(r) for r in readings]


def test_benign_stays_calm():
    s = RiskState(threshold=70)
    events = feed(
        s,
        [
            reading("none", "benign", 0.0),
            reading("none", "benign", 0.0),
            reading("none", "benign", 0.05),
        ],
    )
    assert s.score < 10, s.score
    assert not any(e["should_fire"] for e in events)
    print(f"  benign stays calm: score={s.score:.1f}  ✓")


def test_single_keyword_does_not_fire():
    # One isolated 'payment'-flavored read in an otherwise benign call.
    s = RiskState(threshold=70)
    events = feed(
        s,
        [
            reading("none", "benign", 0.0),
            reading("gift_card", "payment", 0.5, ["mentions a gift card"]),  # one blip
            reading("none", "benign", 0.0),
            reading("none", "benign", 0.0),
        ],
    )
    assert not any(e["should_fire"] for e in events), "single keyword should NOT fire"
    assert s.score < 70, s.score
    print(f"  lone keyword does not fire: peak handled, final score={s.score:.1f}  ✓")


def test_full_trajectory_fires():
    s = RiskState(threshold=70)
    events = feed(
        s,
        [
            reading("none", "benign", 0.1),
            reading("irs_government", "authority", 0.7, ["claims to be IRS"]),
            reading("irs_government", "urgency", 0.8, ["threatens arrest"]),
            reading("irs_government", "secrecy", 0.85, ["says don't hang up"]),
            reading("irs_government", "payment", 0.9, ["wants gift-card codes"], "Do not buy gift cards."),
            reading("irs_government", "payment", 0.92, ["wants gift-card codes"]),
        ],
    )
    assert any(e["should_fire"] for e in events), "full trajectory should fire"
    fire_event = next(e for e in events if e["should_fire"])
    assert fire_event["stage"] in ("secrecy", "payment")
    assert fire_event["score"] >= 70
    assert s.fired
    # Fires exactly once.
    more = s.update(reading("irs_government", "payment", 0.95))
    assert not more["should_fire"], "must not re-fire"
    print(f"  full trajectory fires once at stage={fire_event['stage']} score={fire_event['score']}  ✓")


def test_decay_after_scare():
    s = RiskState(threshold=70)
    feed(
        s,
        [
            reading("tech_support", "authority", 0.7),
            reading("tech_support", "urgency", 0.75),
        ],
    )
    mid = s.score
    feed(s, [reading("none", "benign", 0.0)] * 4)
    assert s.score < mid, (mid, s.score)
    assert not s.fired
    print(f"  decays after a scare: {mid:.1f} -> {s.score:.1f}  ✓")


def test_trajectory_climbs_monotonically_then_peaks():
    s = RiskState(threshold=70)
    scores = []
    for stage, conf in [
        ("authority", 0.7),
        ("urgency", 0.8),
        ("secrecy", 0.85),
        ("payment", 0.9),
    ]:
        e = s.update(reading("bank_impersonation", stage, conf))
        scores.append(e["score"])
    assert scores == sorted(scores), scores
    assert scores[-1] >= 70, scores
    print(f"  meter climbs through stages: {scores}  ✓")


def test_stress_escalates_sooner():
    seq = [("authority", 0.7), ("urgency", 0.8), ("secrecy", 0.85), ("payment", 0.92), ("payment", 0.95)]

    def run(stress):
        s = RiskState(threshold=70)
        fire_idx = None
        for i, (stage, conf) in enumerate(seq):
            e = s.update(reading("irs_government", stage, conf), victim_stress=stress)
            if e["should_fire"] and fire_idx is None:
                fire_idx = i
        return fire_idx

    calm = run(0.05)
    panic = run(0.85)
    assert calm is not None and panic is not None, (calm, panic)
    assert panic <= calm, (panic, calm)
    print(f"  distressed victim fires no later than calm (panic@{panic} ≤ calm@{calm})  ✓")


def test_calm_tempers_stress_boosts():
    seq = [reading("bank_impersonation", "authority", 0.7), reading("bank_impersonation", "urgency", 0.8)]
    calm = RiskState(threshold=70)
    hot = RiskState(threshold=70)
    for r in seq:
        calm.update(r, victim_stress=0.0)
    for r in seq:
        hot.update(r, victim_stress=0.9)
    assert hot.score > calm.score, (calm.score, hot.score)
    print(f"  calm tempers, stress boosts: calm={calm.score:.1f} < stressed={hot.score:.1f}  ✓")


if __name__ == "__main__":
    tests = [
        test_benign_stays_calm,
        test_single_keyword_does_not_fire,
        test_full_trajectory_fires,
        test_decay_after_scare,
        test_trajectory_climbs_monotonically_then_peaks,
        test_stress_escalates_sooner,
        test_calm_tempers_stress_boosts,
    ]
    print("Verifying Sentinel risk state machine:\n")
    for t in tests:
        t()
    print("\nAll risk-machine checks passed ✓")
