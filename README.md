# Sentinel — a voice-native guardian against phone scams

**Sentinel listens to a live phone call, recognizes the social-engineering *trajectory* (claimed authority → manufactured urgency → demand for secrecy → push to an irreversible payment) with an LLM classifier, and reads the victim's vocal *distress* with Hume. Depending on how stressed the victim sounds, it either speaks a specific warning into the call — or *takes over the call* with a conversational agent that confronts the scammer — while texting a family member.**

It's built for the people scammers target most: the elderly and the vulnerable, who can't read a fraud alert in the middle of a frightening call. The only modality that reaches them is the one the scam is happening in — voice.

---

## Why it's a *voice agent*, not a chatbot with a microphone

Sentinel uses **how** you speak, not just what's said, and it can act inside the audio channel:

- **Paralinguistics:** a Hume prosody model reads the victim's vocal distress — the signal a text classifier is structurally blind to, and the thing that lets Sentinel tell "I'll handle this" from "I'm in over my head."
- **Emotion-gated response:** calm victim → a short spoken warning; **distressed victim → Sentinel takes over the call**, bridging the scammer's audio to an ElevenLabs Conversational-AI "guardian" agent that refuses codes/payments, demands the caller identify themselves, and states the call is monitored.
- **Handles interruption / turn-taking** during takeover via ElevenLabs ConvAI.

## What it does

- **Real-time transcription** of the call (Deepgram streaming).
- **Scam classification** with a **two-axis taxonomy** — `scam_type` (the pretext: grandparent, bank, IRS, government-grant, tech-support, refund, delivery, loan, investment/crypto, charity, auto-warranty, job, …) × `payment_vector` (the irreversible ask: gift cards, wire, crypto wallet, bank/card details, OTP code, upfront fee, remote access, courier cash).
- **A staged risk state machine** that fires on the *trajectory*, not a keyword — and fuses the victim's stress so a frightened victim escalates faster while a calm one is tempered (fewer false alarms).
- **Emotion-gated intervention:** spoken warning **or** full call takeover.
- **Multi-channel family alerts:** SMS, **WhatsApp**, or an automated **phone call** that reads the warning aloud (Twilio).
- **A live dashboard:** role-labeled transcript, severity meter, scam-trajectory ladder, victim-stress meter, red-flag chips, a `MONITORING / WARNING / TAKEOVER` mode badge, a live takeover-conversation panel, and an intervention log.

## Architecture

```
                         ┌─ Deepgram (Victim) ─┐
 mic / call audio ──┬──► │                     ├─► merged, role-labeled transcript ─► GPT-4o classifier
 (role-tagged)      │    └─ Deepgram (Caller) ─┘                                        (scam_type +
                    │                                                                    payment_vector + stage)
                    └─ Hume prosody (victim only) ─► victim_stress (0-1) ──┐                    │
                                                                           ▼                    ▼
                                                                    ┌──────────── FUSED risk state machine ───┐
                                                                    │  authority → urgency → secrecy → payment │
                                                                    └───────────────────┬──────────────────────┘
                                                                          fire │  (stress-gated)
                                                            ┌──────────────────┴───────────────────┐
                                                     victim CALM                            victim STRESSED
                                                  spoken warning (ElevenLabs TTS)     TAKEOVER: bridge caller audio ↔
                                                            │                          ElevenLabs ConvAI guardian agent
                                                            └────────────► family alert (SMS / WhatsApp / call) ◄─────┘
```

## Tech stack

| Layer | Choice |
|------|--------|
| Backend | Python · FastAPI · WebSockets |
| Streaming ASR | Deepgram (`nova-2`, raw WebSocket) |
| Scam classifier | OpenAI **GPT-4o** (structured JSON output) |
| Victim emotion | **Hume** Expression Measurement (prosody) |
| Spoken warning | ElevenLabs TTS |
| Call takeover | ElevenLabs **Conversational AI** (Agents) |
| Family alerts | Twilio (SMS / WhatsApp / Voice) |
| Frontend | React · Vite · TypeScript |

## Quick start

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in keys (all optional — see below)
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

Open the dashboard. With **zero keys** you can already click the **demo buttons**; add keys to light up live transcription, classification, voice, emotion, and alerts.

## API keys (`backend/.env`)

| Key(s) | Enables | Notes |
|--------|---------|-------|
| `DEEPGRAM_API_KEY` | Live transcription | free credits on signup |
| `OPENAI_API_KEY` (`OPENAI_MODEL`, default `gpt-4o`) | Scam classifier | |
| `HUME_API_KEY` | Victim emotion (prosody) | metered (~$0.06/min) |
| `ELEVENLABS_API_KEY` (`ELEVENLABS_VOICE_ID`) | Spoken warning **+** call takeover | takeover needs the key's **ElevenAgents → Write** permission; free voices only on the free tier |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | Family alerts | |
| `TWILIO_ALERT_CHANNELS` | `sms` / `whatsapp` / `call` (comma-separated) | US SMS is often blocked by A2P 10DLC; WhatsApp sandbox is the easy path |
| `TWILIO_FROM_NUMBER`, `FAMILY_ALERT_NUMBER` | SMS + voice-call alerts | trial: destination must be a **verified** number |
| `TWILIO_WHATSAPP_FROM`, `FAMILY_WHATSAPP_NUMBER` | WhatsApp alerts | recipient must `join` the Twilio WhatsApp sandbox first |

Tunables: `SENTINEL_RISK_THRESHOLD` (default 70), `STRESS_TAKEOVER_THRESHOLD` (default 0.55), `DEEPGRAM_MODEL`, `DEEPGRAM_DIARIZE`.

**Degraded mode:** every integration is optional — Sentinel boots with none, and the capability dots (ASR / Classifier / Emotion / Voice / SMS) light up as each key is added. Missing keys simply skip their step.

## Using it (solo, one mic)

Sentinel runs the two call parties as two roles. For a solo demo, use the footer **role toggle**:

1. Click **● Start listening**.
2. Toggle **🎭 Caller** and read the scammer's lines → transcribed as *Caller*; the risk meter climbs. (Sample escalating scripts are easy to find / generate.)
3. Toggle **🧓 Victim** and voice the victim — **calm or panicked**. Only victim audio reaches Hume.
4. At the payment stage: **calm victim → spoken warning; stressed victim → TAKEOVER** (the guardian agent talks to the caller; the mic auto-tags Caller so you answer as the scammer), plus a family alert.

Or use the **demo buttons** (no mic/keys needed): **Scam (calm)** → warning branch, **Scam (distressed)** → takeover branch, **Normal call** → stays quiet (false-positive guard).

## Verifying

```bash
cd backend && source .venv/bin/activate
python verify_risk.py            # unit-checks the risk machine incl. stress fusion
python ws_smoke.py               # drives the full WS pipeline (needs the server running)
python eval_classifier.py        # precision/recall of the classifier on the labeled dataset
```

On the bundled labeled dataset the two-axis classifier scores ~**0.98 precision / 1.00 recall / 0.99 F1**, with the "unknown" (uncovered) rate down from 40% → ~15% after the taxonomy rebuild.

## Repo layout

```
backend/app/
  taxonomy.py      # two-axis scam taxonomy (scam_type × payment_vector)   ← core IP
  risk.py          # staged risk state machine + stress fusion             ← core IP
  classifier.py    # GPT-4o structured-JSON classifier
  asr.py           # Deepgram live streaming (raw WebSocket, diarization)
  hume.py          # victim-emotion (prosody) signal
  intervention.py  # spoken warning + family alerts (SMS / WhatsApp / call)
  takeover.py      # ElevenLabs Conversational-AI guardian agent
  session.py       # per-call state (transcript window, risk, stress, mode)
  main.py          # FastAPI app + paired-client session orchestration
  Data/            # labeled scam / non-scam dataset
frontend/src/      # React dashboard + the caller-mic page
docs/build-plan.md # original build plan
```

## Roadmap / honest limitations

- **Real 2-way phone call** via Twilio Programmable Voice + **Media Streams** is the production endpoint — separate audio legs (clean victim/caller split) and a true full-duplex barge-in takeover. The current build is a browser demo with a single-mic role toggle.
- Single live session at a time (demo-grade); Twilio sandboxes are time-limited; browser mic capture needs a secure context.
- This is a defensive / educational prototype — not a shipped product.
