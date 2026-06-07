import { riskColor } from '../lib/ui';

type Props = {
  score: number;
  threshold: number;
  fired: boolean;
};

export function SeverityMeter({ score, threshold, fired }: Props) {
  const color = riskColor(score);
  return (
    <div className={`meter ${fired ? 'meter--fired' : ''}`}>
      <div className="meter__head">
        <span className="meter__kicker">Severity</span>
        <span className="meter__num" style={{ color }}>
          {Math.round(score)}
          <i>/100</i>
        </span>
      </div>

      <div className="meter__track">
        <div
          className="meter__fill"
          style={{
            height: `${score}%`,
            background: `linear-gradient(180deg, ${color}, ${color}66)`,
            boxShadow: `0 0 24px ${color}88`,
          }}
        />
        <div
          className="meter__threshold"
          style={{ bottom: `${threshold}%` }}
          title={`Intervention threshold (${threshold})`}
        >
          <span>fire ▸ {threshold}</span>
        </div>
      </div>
    </div>
  );
}
