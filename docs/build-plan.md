# Sentinel — Build Plan

**Cross-platform live scam-interception guardian for vulnerable callers.**

A passive in-call listener that recognizes social-engineering scam scripts as they unfold (grandparent scam, fake-bank/IRS, tech support, gift-card / pig-butchering) and intervenes mid-call — warning the user and optionally alerting a family member.

This plan is optimized for a **working demo by end of day**, not for production correctness.

---

## Architecture overview

```
Call audio  ──►  Streaming ASR  ──►  Scam classifier + risk score (CORE)
(recorded     (Deepgram,           (LLM + staged risk state machine)
 WAV or        rolling text)              │
 Twilio)                                  │ risk ≥ threshold
                                          ▼
                        ┌─────────────────┼─────────────────┐
                        ▼                 ▼                 ▼
                  Voice warning      Family SMS        Live dashboard
                  (TTS into ear)     (Twilio alert)    (React meter)

The classifier is fed by a pre-loaded scam taxonomy:
~15 scripts (grandparent, IRS, tech support), staged by
urgency → secrecy → payment coercion.
```

---

## Stack, component by component

### Audio channel — fake the phone, don't tap it
Real iOS/Android call-audio access is locked down and would eat the whole day. Two options instead:

- **Safe (do this first):** a browser/desktop app that plays a recorded scam call (or a live two-person role-play) into the mic and captures it with `getUserMedia`. This is the guaranteed demo.
- **Impressive (add if time allows):** Twilio Programmable Voice + Media Streams — call a real Twilio number, and it forks the live call audio to the backend over a websocket.

Either way, Twilio also handles the family-SMS alert, so it earns its place.

### Streaming speech-to-text — use a managed API, not self-hosted
Parakeet / Canary via NVIDIA Riva are excellent but self-hosting Riva with GPU setup costs hours you don't have.

- **For a one-day build:** `Deepgram` streaming is the path of least resistance — websocket in, partial transcripts out, sub-300ms, generous free credits.
- **Equally good alternative:** `AssemblyAI` streaming.
- Keep **Parakeet / Riva as the "production roadmap"** answer for judges who ask about cost at scale.

### The classifier — this is the actual IP, spend the time here
A fast LLM (`GPT-4o-mini`, `Claude Haiku`, or `gpt-4.1-mini`) gets the rolling transcript window plus the pre-loaded scam taxonomy, and returns structured JSON:

```json
{
  "scam_type": "...",
  "stage": "...",
  "confidence": 0.0,
  "red_flags": ["..."],
  "recommended_action": "..."
}
```

Wrap it in a simple running **risk-score state machine** — risk accumulates as the call moves through stages:

> claimed authority → manufactured urgency → demand for secrecy → push toward an irreversible payment (gift cards, wire, crypto, or reading out an OTP)

**Don't fire on a single keyword; fire when the trajectory matches.** That staged-scoring logic is what separates this from a spam-word filter, and it's what to demo explicitly.

### Intervention
When the score crosses the threshold:

- A **TTS warning** (`ElevenLabs`, `Cartesia`, or `OpenAI TTS`) speaks a short, **specific** instruction — not "this may be a scam" but "do not read them that code."
- A **Twilio SMS** goes to the designated family member with a one-line summary.

The specificity is the product; generic warnings get ignored.

### Frontend
A small React or plain-HTML dashboard showing:

- the live transcript,
- the severity meter climbing in real time,
- the red-flag chips lighting up,
- an intervention log.

This is what judges actually watch, so make the meter movement legible.

### Orchestration shortcut worth knowing
`Pipecat` (open-source, by Daily) or `LiveKit Agents` handle the STT→LLM→TTS audio plumbing, VAD, and websocket transport.

The catch: they're built for the agent being a *participant* in the call, whereas Sentinel is a passive third listener — so you'd use them in a slightly unusual way (route audio in, run the classifier as a custom processor, only emit TTS on threshold). If the team already knows one of them, use it; if not, rolling your own with the Deepgram SDK + an LLM call + Twilio is probably faster than learning the framework under time pressure.

---

## Time budget for the day

| Hours | Focus |
|-------|-------|
| 0–1   | Decide scope, get Deepgram + OpenAI/Anthropic + Twilio keys working, confirm audio capture into backend |
| 1–3   | Streaming ASR → rolling transcript displayed live in the dashboard |
| 3–6   | The classifier + scam taxonomy + risk-score state machine (the core; protect this time) |
| 6–8   | Intervention path: TTS warning + Twilio SMS firing on threshold |
| 8–9   | Dashboard polish: severity meter, red-flag chips, intervention log |
| 9–10  | Record 2–3 scam-call clips, rehearse the demo, tune the threshold so it fires at the right dramatic moment |

---

## The two things most likely to sink the build

1. **Spending too long trying to access real call audio** — don't; simulate it.
2. **A jumpy threshold that fires on benign talk** — hand-tune it against the recorded clips until it triggers cleanly on the payment-coercion moment and stays quiet before.
