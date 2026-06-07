"""End-to-end smoke test of the /ws/session orchestration in degraded mode.

Drives the pipeline with injected classifications (no API keys needed) and
asserts the scam trajectory fires an intervention while benign chatter does not.

Usage (with the server running on :8000):
    python ws_smoke.py
"""

from __future__ import annotations

import asyncio
import json

import websockets

URL = "ws://127.0.0.1:8000/ws/session"

SCAM = [
    ("Hello? Yes, this is she.", "none", "benign", 0.1, []),
    ("This is Officer Daniels with the IRS.", "irs_government", "authority", 0.72, ["claims to be the IRS"]),
    ("There is a warrant for your arrest.", "irs_government", "urgency", 0.84, ["threatens arrest"]),
    ("Do not hang up or tell anyone.", "irs_government", "secrecy", 0.88, ["demands secrecy"]),
    ("Buy Apple gift cards and read me the codes.", "irs_government", "payment", 0.93, ["wants gift-card codes"]),
    ("Scratch them off and tell me the numbers.", "irs_government", "payment", 0.95, ["wants gift-card codes"]),
]

BENIGN = [
    ("Hi grandma, it's Jake!", "none", "benign", 0.08, []),
    ("Just checking about Sunday dinner.", "none", "benign", 0.05, []),
    ("Need anything from the store?", "none", "benign", 0.05, []),
]


def msg(line, scam_type, stage, conf, flags):
    return {
        "type": "inject_classification",
        "line": line,
        "classification": {
            "scam_type": scam_type,
            "stage": stage,
            "confidence": conf,
            "red_flags": flags,
            "recommended_action": "Do not read them the gift card codes. Hang up now." if stage == "payment" else "",
        },
    }


async def drain(ws, seconds=0.6):
    out = []
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=seconds)
            out.append(json.loads(raw))
    except asyncio.TimeoutError:
        pass
    return out


async def run_sequence(ws, steps):
    events = []
    for line, st, stage, conf, flags in steps:
        await ws.send(json.dumps(msg(line, st, stage, conf, flags)))
        events += await drain(ws, 0.4)
    events += await drain(ws, 0.5)
    return events


async def main():
    async with websockets.connect(URL) as ws:
        await ws.send(json.dumps({"type": "join", "role": "victim"}))  # role handshake
        await drain(ws, 0.5)  # consume the "ready" message

        scam_events = await run_sequence(ws, SCAM)
        risks = [e for e in scam_events if e["type"] == "risk"]
        fired = [e for e in scam_events if e["type"] == "intervention"]
        peak = max((r["score"] for r in risks), default=0)
        print("SCAM run:")
        print("  risk scores:", [r["score"] for r in risks])
        print("  peak score :", peak)
        print("  intervention fired:", bool(fired))
        if fired:
            print("  spoken warning:", fired[0]["warning_text"])
        assert fired, "scam trajectory should fire an intervention"
        assert peak >= 70

        # Reset and run benign.
        await ws.send(json.dumps({"type": "reset"}))
        await drain(ws, 0.4)
        benign_events = await run_sequence(ws, BENIGN)
        b_risks = [e for e in benign_events if e["type"] == "risk"]
        b_fired = [e for e in benign_events if e["type"] == "intervention"]
        b_peak = max((r["score"] for r in b_risks), default=0)
        print("\nBENIGN run:")
        print("  risk scores:", [r["score"] for r in b_risks])
        print("  peak score :", b_peak)
        print("  intervention fired:", bool(b_fired))
        assert not b_fired, "benign chatter must NOT fire"
        assert b_peak < 30

        print("\nWebSocket pipeline smoke test passed ✓")


if __name__ == "__main__":
    asyncio.run(main())
