import type { Stage } from '../lib/types';
import { STAGE_ORDER, STAGE_LABEL } from '../lib/ui';

const RANK: Record<Stage, number> = {
  benign: 0,
  authority: 1,
  urgency: 2,
  secrecy: 3,
  payment: 4,
};

export function StageLadder({ stage }: { stage: Stage }) {
  const reached = RANK[stage];
  return (
    <div className="ladder">
      <span className="ladder__kicker">Scam trajectory</span>
      <ol>
        {STAGE_ORDER.map((s, i) => {
          const idx = i + 1;
          const active = reached === idx;
          const passed = reached > idx;
          return (
            <li
              key={s}
              className={`ladder__step ${passed ? 'is-passed' : ''} ${
                active ? 'is-active' : ''
              }`}
            >
              <span className="ladder__dot" />
              <span className="ladder__label">{STAGE_LABEL[s]}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
