# Sentinel

Cross-platform live scam-interception guardian. A passive in-call listener that
recognizes social-engineering scam scripts as they unfold (grandparent, fake
bank/IRS, tech support, gift-card / pig-butchering) and intervenes mid-call —
speaking a specific spoken warning into the user's ear and texting a family
member.

```
Browser mic ─► FastAPI /ws/session ─► Deepgram ASR ─► GPT-4o-mini classifier
                                                         │
                                                  Risk state machine
                                          (authority→urgency→secrecy→payment)
                                                         │ risk ≥ threshold
                                              ┌──────────┴──────────┐
                                        ElevenLabs TTS        Twilio SMS
                                        (spoken warning)     (family alert)
                                                         │
                                          React dashboard (meter, chips, log)
```

## Quick start

### 1. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill in keys (optional — see below)
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

Open the dashboard, then either click **● Start listening** (uses your mic) or
hit **▶ Play scam call** in the demo cluster.

## Degraded mode (no keys)

Sentinel boots and runs **without any API keys**. In that mode:

- the **Demo** buttons drive the full pipeline (risk meter, stage ladder, red
  flags, intervention banner) with zero keys — great for a first look;
- live microphone transcription, the GPT-4o-mini classifier, the spoken TTS
  warning, and the family SMS are skipped until their keys are present.

The dashboard's capability dots (ASR / Classifier / Voice / SMS) light up as
each key is configured.

## API keys (`backend/.env`)

| Key | Enables |
|-----|---------|
| `DEEPGRAM_API_KEY` | Live microphone transcription |
| `OPENAI_API_KEY` | The GPT-4o-mini scam classifier |
| `ELEVENLABS_API_KEY` (+ optional `ELEVENLABS_VOICE_ID`) | The spoken in-call warning |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `FAMILY_ALERT_NUMBER` | The family-alert SMS |

> Twilio trial accounts can only text **verified** numbers — verify the demo
> phone in the Twilio console first.

Tunables (also in `.env`): `SENTINEL_RISK_THRESHOLD` (default 70),
`DEEPGRAM_MODEL` (default `nova-2`).

## Verifying without keys

```bash
cd backend && source .venv/bin/activate
python verify_risk.py     # unit-checks the staged risk state machine
# in another shell, with the server running:
python ws_smoke.py        # drives the full WS pipeline (scam fires, benign doesn't)
```

## Layout

- `backend/app/taxonomy.py` — the scam taxonomy (staged scripts). **Core IP.**
- `backend/app/risk.py` — the staged risk state machine. **Core IP.**
- `backend/app/classifier.py` — GPT-4o-mini structured-JSON classifier.
- `backend/app/asr.py` — Deepgram live streaming (raw WebSocket).
- `backend/app/intervention.py` — ElevenLabs TTS + Twilio SMS.
- `backend/app/main.py` — FastAPI app + `/ws/session` orchestration.
- `frontend/src/` — the React dashboard.
