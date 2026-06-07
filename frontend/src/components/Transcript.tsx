import { useEffect, useRef } from 'react';

export type Line = { text: string; speaker: number | null; label?: string };

type Props = {
  finals: Line[];
  interim: string;
  listening: boolean;
  asrEnabled: boolean;
};

const SPEAKER_COLORS = ['var(--safe)', 'var(--alarm)', 'var(--grape)', 'var(--watch)'];

export function Transcript({ finals, interim, listening, asrEnabled }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [finals.length, interim]);

  const empty = finals.length === 0 && !interim;

  return (
    <div className="transcript">
      <div className="panel__head">
        <span className="panel__kicker">Live transcript</span>
        {listening && <span className="panel__pulse" />}
      </div>
      <div className="transcript__body">
        {empty && listening && !asrEnabled && (
          <div className="transcript__notice">
            <p className="transcript__notice-title">🎙️ Listening — mic is on</p>
            <p>
              Live transcription needs a Deepgram key. Add{' '}
              <code>DEEPGRAM_API_KEY</code> to <code>backend/.env</code> and
              restart the backend.
            </p>
            <p className="transcript__notice-dim">
              No key yet? Try the demo buttons below — they don't need one.
            </p>
          </div>
        )}
        {empty && listening && asrEnabled && (
          <p className="transcript__empty">🎙️ Listening… start speaking.</p>
        )}
        {empty && !listening && (
          <p className="transcript__empty">
            Click <b>Start listening</b> to transcribe a live call, or run a
            demo below.
          </p>
        )}
        {finals.map((line, i) => (
          <p key={i} className="transcript__line">
            {line.speaker != null ? (
              <span
                className="transcript__speaker"
                style={{ color: SPEAKER_COLORS[line.speaker % SPEAKER_COLORS.length] }}
              >
                {line.label ?? `S${line.speaker}`}
              </span>
            ) : (
              <span className="transcript__caret">›</span>
            )}{' '}
            {line.text}
          </p>
        ))}
        {interim && (
          <p className="transcript__line transcript__line--interim">
            <span className="transcript__caret">›</span> {interim}
          </p>
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}
