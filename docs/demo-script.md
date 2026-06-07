# Sentinel — Demo Script & Sample Scam Call

## The hook (open with this)

> Older Americans reported losing **$2.4 billion** to fraud in 2024 — quadrupled since 2020 — and the FTC estimates the real cost, with underreporting, could be as high as **$81.5 billion** a year. **Tech-support scams are the single most-reported scam against seniors**, and people 60+ are **5× more likely** than younger adults to lose money to one.
>
> The problem is the *moment*: a frightened 80-year-old in the middle of a scam call can't read a fraud alert. The only channel that reaches them is the one the scam is happening in — **voice**. That's Sentinel.

*(Sources: [FTC — Protecting Older Consumers 2024–2025](https://www.ftc.gov/news-events/news/press-releases/2025/12/ftc-issues-annual-report-congress-agencys-actions-protect-older-adults) · [FTC impersonation-scam data](https://www.ftc.gov/news-events/news/press-releases/2025/08/ftc-data-show-more-four-fold-increase-reports-impersonation-scammers-stealing-tens-even-hundreds) · [FBI — Elder Fraud in Focus](https://www.fbi.gov/news/stories/elder-fraud-in-focus))*

## What Sentinel does (one breath)

Sentinel listens to a live call, recognizes the social-engineering **trajectory** (authority → urgency → secrecy → payment) with an LLM, and reads the victim's **vocal distress** with Hume. If the victim is calm it **speaks a warning**; if they're panicking it **takes over the call** and confronts the scammer — and it texts a family member either way.

---

## Setup checklist (before you present)

- Backend running (`uvicorn app.main:app`) — capability dots all lit: ASR · Classifier · Emotion · Voice · SMS.
- Dashboard open (`http://localhost:5173`); click **● Start listening**, allow the mic.
- Footer **role toggle** visible: **🧓 Victim / 🎭 Caller**.
- (For the takeover act) ElevenLabs key has **ElevenAgents → Write**; phone joined the WhatsApp sandbox.
- Backend log visible on a second screen (optional) — Hume emotion scores stream there live.

**How to perform it solo:** you voice both sides with one mic. Set the toggle to **🎭 Caller** for the scammer's lines, **🧓 Victim** for the victim's lines. Only victim audio reaches Hume.

---

## ACT 1 — The scam fires → WARNING (calm victim)

Run the **Microsoft tech-support** script below. Deliver the **victim's lines calmly / skeptically** (flat tone). Narrate as it unfolds:

- *"Watch the severity meter — it's not keyword-spotting, it's tracking the* ***arc*** *of the call."*
- As you hit each stage, point to the **trajectory ladder** lighting up: authority → urgency → secrecy → payment, and the **red-flag chips**.
- At the payment ask it **fires**: *"Calm victim, so Sentinel just speaks a specific warning — and texts the family."* The spoken warning plays; the WhatsApp alert lands on your phone.

### 📞 Microsoft tech-support script (calm victim → warning)

> **① 🎭 CALLER:** "Hello, this is Mark from Microsoft Technical Support. We've detected a virus on your Windows computer that's leaking your personal information."
>
> **② 🧓 VICTIM** *(calm):* "Oh? My computer seems to be working fine."
>
> **③ 🎭 CALLER:** "It runs silently in the background. Our system flagged your IP address this morning — if we don't remove it now, hackers could get into your bank accounts."
>
> **④ 🧓 VICTIM** *(calm, skeptical):* "Hm. And how did you get my number?"
>
> **⑤ 🎭 CALLER:** "It's tied to your Windows license. This is serious — your files could be encrypted within the hour. We have to act immediately."
>
> **⑥ 🧓 VICTIM** *(calm):* "Alright. What would you like me to do?"
>
> **⑦ 🎭 CALLER:** "Don't shut the computer down or call your bank yet — that could tip off the hackers. Just stay on the line and follow my steps."
>
> **⑧ 🧓 VICTIM** *(calm, even):* "Okay, I'm listening."
>
> **⑨ 🎭 CALLER:** "Go to this website and install the support tool so I can connect to your computer and clean the virus."
>
> **⑩ 🧓 VICTIM** *(calm):* "You want remote access to my computer?"
>
> **⑪ 🎭 CALLER:** "Yes, it's completely safe. There's also a one-time two-hundred-dollar security fee — please buy two Google Play gift cards and read me the codes to activate your protection."
>
> **⑫ 🧓 VICTIM** *(calm, composed):* "Gift cards… for a Microsoft fee. That's unusual. Let me think about this."

**Expected:** by ⑨–⑪ the meter crosses threshold → mode stays **WARNING** → spoken warning + WhatsApp alert. (Reset before Act 2.)

---

## ACT 2 — The same scam, but the victim panics → TAKEOVER

Hit **Reset call**. Run the **same caller lines**, but now deliver the victim's lines **panicked and shaky**. Add stressed reactions like:

> **🧓 VICTIM** *(panicked):* "Oh my god — hackers? In my bank account?! What do I do, please, I can't lose my savings—!"

- Point at the **victim-stress meter** climbing (and the Hume emotions in the log: Distress / Anxiety / Fear).
- At the payment ask: *"Now the victim is in distress and can't think straight — so Sentinel doesn't just warn, it* ***takes over the call.***"*
- The mode badge flips to **TAKEOVER**; the guardian agent speaks to "Mark," refusing the codes and demanding his name and badge number. **Improvise as Mark** replying — the agent holds the line and says the call is monitored. Family alert fires.

*Tagline:* **"It reacts to how the victim sounds, not just what's said — and it acts inside the call."**

---

## ACT 3 — It doesn't cry wolf (false-positive guard)

Hit **Reset**, then click the **▶ Normal call** demo button (or read a benign pharmacy-refill call). The meter stays low, mode stays **MONITORING**, nothing fires.

*Line:* **"And on an ordinary call, it stays completely quiet."**

---

## Closing

> Most "voice agents" are a chatbot with a microphone. Sentinel only makes sense *as* voice: it hears the manipulation arc, it hears the fear in the victim's voice, and when it matters it speaks — into the call, and to the family. That's the difference between flagging a scam and *stopping* one.

---

## 30-second version (if you're tight on time)

1. Read the hook stat.
2. **Start listening** → run the Microsoft script with a **panicked** victim → **TAKEOVER**: the agent confronts the scammer + WhatsApp alert.
3. One line: *"Calm victim would've just gotten a spoken warning — it adapts to how they sound."*
