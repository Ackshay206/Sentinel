export type LogEntry = {
  ts: string;
  kind: 'warning' | 'sms';
  text: string;
  ok?: boolean;
};

export function InterventionLog({ entries }: { entries: LogEntry[] }) {
  return (
    <div className="log">
      <div className="panel__head">
        <span className="panel__kicker">Intervention log</span>
      </div>
      <div className="log__body">
        {entries.length === 0 ? (
          <p className="log__empty">No interventions fired.</p>
        ) : (
          entries.map((e, i) => (
            <div key={i} className={`log__row log__row--${e.kind}`}>
              <span className="log__time">{e.ts}</span>
              <span className="log__icon">
                {e.kind === 'warning' ? '🔊' : e.ok ? '✉️' : '⚠️'}
              </span>
              <span className="log__text">{e.text}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
