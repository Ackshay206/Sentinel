# Sentinel vs. "What Makes a Voice Agent" — Rubric Comparison

*Comparing Sentinel as currently built against the "Voice Agents — what they are and aren't" rubric.*

## Verdict in one line
Sentinel **passes the rubric's most important test and fails its most specific one.** It is a voice-native *use case* implemented as a *text pipeline*.

## The rubric

**NOT a voice agent:** chatbot with a microphone · STT → LLM → TTS wrapper · text UI you can yell at · ignores how you speak

**A voice agent:** only makes sense as voice · hears tone, pace, silence · handles interruption · frictionless where text fails

**The filter:** can you answer "why voice?" in one sentence?

## Criterion-by-criterion

| Slide criterion | Sentinel as built | Why |
|---|---|---|
| "only makes sense as voice" | **Pass (strong)** | The threat is a live phone call to a vulnerable person. There is no text version of this problem. |
| "frictionless where text fails" | **Pass (strong)** | A panicking elderly victim mid-scam can't read a text notification. A spoken warning into the call is the only modality that lands. |
| can you answer "why voice?" in one sentence | **Pass** | "Because the scam is delivered live over a phone call, so the only way to stop it is to be inside the audio channel and speak a warning the victim actually hears." |
| "hears tone, pace, silence" | **Fail** | The classifier only ever sees `transcript_window` — text. `asr.py` configures Deepgram for `punctuate` / `smart_format` / `endpointing`; the only handling of silence is a keepalive ping. No prosody, stress, or pause signal reaches the model. |
| "ignores how you speak" → should use *how* | **Fail** | It reasons entirely about *what* is said (tactics, paraphrases, claimed authorities). It discards *how* it's said. |
| "not an STT → LLM → TTS wrapper" | **Fail (literally)** | The pipeline is mic → Deepgram (STT) → GPT-4o-mini on text (LLM) → ElevenLabs/Twilio (TTS). That's the exact shape the slide red-flags. |
| "handles interruption" | **N/A / partial** | It's a passive co-listener, so being interrupted doesn't apply — but the warning also doesn't truly barge into the live call yet (full-duplex was deliberately deferred). |

## The takeaway

On the left column of the slide, Sentinel currently sits in two of the four "NOT a voice agent" boxes — it's a chatbot-with-a-microphone on the **input** side. The scenario is voice; the implementation treats the call as a transcript.

This is not a pedantic ding. `diff-and-demo-brief.md` already flags that the ASR → LLM → warning loop is heavily built (Google, Hiya, Samsung all ship it) and that Sentinel must "win on execution, not novelty." The answer to *what makes Sentinel un-clonable by a text-based fraud classifier* is hiding in the exact box it's failing: **tone, pace, silence.**

- A scam victim under coercion has detectable distress prosody — stress, fear, the long hesitant pause before "okay, what's the code?"
- A scammer reading a script has detectable cadence and call-center / VOIP artifacts.
- None of this survives transcription — so a pure-text pipeline (Sentinel's, and the incumbents') is structurally blind to it.

That paralinguistic layer is the one signal a text classifier categorically cannot replicate. **The change that moves Sentinel from the left column to the right column of the slide is the same change that gives it the defensible moat the brief is searching for.**

## Recommended fix

1. **Add an emotion / prosody signal to the risk state machine.** Use Hume EVI on the audio stream, or Deepgram sentiment/emotion features plus a simple pause-duration detector.
2. **Fuse it with the existing transcript-based stage score.** Distress prosody + a payment-stage transcript should fire faster and more confidently than transcript alone; calm prosody should temper false positives.
3. **Result:** "hears tone, pace, silence" becomes true, "ignores how you speak" becomes false, and the architecture stops being an STT → LLM → TTS wrapper and starts using the audio channel for what only the audio channel can provide.
4. **Secondary upgrade — "handles interruption":** make the spoken warning genuinely barge into the live call (the deferred full-duplex piece) rather than playing after a turn.

## Net
Most hackathon "voice agents" fail the *why voice?* filter outright — Sentinel passes it cleanly. But by the strict definition on the slide, what's built today is a voice-shaped text pipeline, and the gap it exposes is precisely where the differentiation should live.
