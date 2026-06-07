export type TakeoverLine = { role: 'agent' | 'caller'; text: string };

export function TakeoverPanel({ messages }: { messages: TakeoverLine[] }) {
  return (
    <div className="takeover">
      <div className="panel__head">
        <span className="panel__kicker takeover__kicker">⚡ Sentinel has taken over the call</span>
      </div>
      <div className="takeover__body">
        {messages.length === 0 ? (
          <p className="takeover__empty">Connecting the guardian agent…</p>
        ) : (
          messages.map((m, i) => (
            <div key={i} className={`takeover__row takeover__row--${m.role}`}>
              <span className="takeover__who">{m.role === 'agent' ? 'Sentinel' : 'Caller'}</span>
              <span className="takeover__text">{m.text}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
