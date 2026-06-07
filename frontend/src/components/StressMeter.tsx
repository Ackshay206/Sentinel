import { riskColor } from '../lib/ui';

type Props = {
  stress: number; // 0-1
  emotions: Record<string, number>;
};

export function StressMeter({ stress, emotions }: Props) {
  const pct = Math.round(stress * 100);
  const color = riskColor(pct);
  const top = Object.entries(emotions)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);

  return (
    <div className="stress">
      <div className="stress__head">
        <span className="stress__kicker">Victim voice · stress</span>
        <span className="stress__num" style={{ color }}>{pct}</span>
      </div>
      <div className="stress__track">
        <div className="stress__fill" style={{ width: `${pct}%`, background: color, boxShadow: `0 0 12px ${color}` }} />
      </div>
      <div className="stress__emotions">
        {top.length === 0 ? (
          <span className="stress__none">listening to how they sound…</span>
        ) : (
          top.map(([name, score]) => (
            <span key={name} className="stress__chip">{name} {(score * 100).toFixed(0)}</span>
          ))
        )}
      </div>
    </div>
  );
}
