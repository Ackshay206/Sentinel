import { useRef, useState } from 'react';
import type { Classification } from '../lib/types';

type Step = { line: string; cls: Classification };

// A scripted IRS → gift-card scam that walks the full arc. Drives the pipeline
// with zero API keys (sent as inject_classification), so the demo always works.
const SCAM: Step[] = [
  {
    line: 'Hello? Yes, this is she.',
    cls: { scam_type: 'none', stage: 'benign', confidence: 0.1, red_flags: [], recommended_action: '' },
  },
  {
    line: "Ma'am, this is Officer Daniels with the IRS enforcement division.",
    cls: { scam_type: 'irs_government', stage: 'authority', confidence: 0.72, red_flags: ['claims to be the IRS'], recommended_action: '' },
  },
  {
    line: 'There is a warrant out for your arrest over unpaid back taxes.',
    cls: { scam_type: 'irs_government', stage: 'urgency', confidence: 0.84, red_flags: ['threatens arrest', 'manufactured urgency'], recommended_action: '' },
  },
  {
    line: 'Do not hang up and do not tell anyone — this is a confidential federal matter.',
    cls: { scam_type: 'irs_government', stage: 'secrecy', confidence: 0.88, red_flags: ['says do not hang up', 'demands secrecy'], recommended_action: '' },
  },
  {
    line: 'Go buy Apple gift cards and read me the codes to clear the warrant.',
    cls: { scam_type: 'irs_government', stage: 'payment', confidence: 0.93, red_flags: ['wants gift-card codes'], recommended_action: 'Do not buy gift cards or read anyone the codes. Hang up and call the IRS using the number on their official website.' },
  },
  {
    line: 'Just scratch off the back and tell me the numbers — stay on the line.',
    cls: { scam_type: 'irs_government', stage: 'payment', confidence: 0.95, red_flags: ['wants gift-card codes', 'pressure to stay on the line'], recommended_action: 'Do not read them the gift card numbers. Hang up now.' },
  },
];

const BENIGN: Step[] = [
  { line: "Hi grandma, it's Jake!", cls: { scam_type: 'none', stage: 'benign', confidence: 0.08, red_flags: [], recommended_action: '' } },
  { line: 'Just calling to check about Sunday dinner.', cls: { scam_type: 'none', stage: 'benign', confidence: 0.05, red_flags: [], recommended_action: '' } },
  { line: 'Mom asked if you need anything from the store.', cls: { scam_type: 'none', stage: 'benign', confidence: 0.05, red_flags: [], recommended_action: '' } },
];

type Props = {
  onStep: (line: string, cls: Classification) => void;
  onReset: () => void;
  onStress: (value: number) => void;
  disabled?: boolean;
};

export function DemoPanel({ onStep, onReset, onStress, disabled }: Props) {
  const [playing, setPlaying] = useState<string | null>(null);
  const timers = useRef<number[]>([]);

  const clearTimers = () => {
    timers.current.forEach((t) => clearTimeout(t));
    timers.current = [];
  };

  const play = (name: string, steps: Step[], stress = 0) => {
    if (disabled) return;
    clearTimers();
    onReset();
    setPlaying(name);
    if (stress > 0) onStress(stress);  // simulate a distressed victim → takeover branch
    steps.forEach((s, i) => {
      const t = window.setTimeout(() => {
        if (stress > 0) onStress(stress);  // keep stress high across the run
        onStep(s.line, s.cls);
        if (i === steps.length - 1) setPlaying(null);
      }, 350 + i * 1700);
      timers.current.push(t);
    });
  };

  return (
    <div className="demo">
      <span className="demo__kicker">Demo (no keys needed)</span>
      <div className="demo__row">
        <button
          className="btn btn--scam"
          disabled={disabled || playing !== null}
          onClick={() => play('scam', SCAM)}
        >
          {playing === 'scam' ? '▸ playing…' : '▶ Scam (calm)'}
        </button>
        <button
          className="btn btn--scam"
          disabled={disabled || playing !== null}
          onClick={() => play('distress', SCAM, 0.8)}
          title="Same scam, but the victim sounds distressed → Sentinel takes over the call"
        >
          {playing === 'distress' ? '▸ playing…' : '▶ Scam (distressed)'}
        </button>
        <button
          className="btn btn--calm"
          disabled={disabled || playing !== null}
          onClick={() => play('benign', BENIGN)}
        >
          {playing === 'benign' ? '▸ playing…' : '▶ Normal call'}
        </button>
        <button
          className="btn btn--ghost"
          disabled={disabled}
          onClick={() => {
            clearTimers();
            setPlaying(null);
            onReset();
          }}
        >
          Reset
        </button>
      </div>
    </div>
  );
}
