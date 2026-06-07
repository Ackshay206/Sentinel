export function RedFlagChips({ flags }: { flags: string[] }) {
  return (
    <div className="chips">
      <span className="chips__kicker">Red flags</span>
      <div className="chips__row">
        {flags.length === 0 ? (
          <span className="chips__none">none yet</span>
        ) : (
          flags.map((f, i) => (
            <span
              key={f + i}
              className="chip"
              style={{ animationDelay: `${i * 60}ms` }}
            >
              {f}
            </span>
          ))
        )}
      </div>
    </div>
  );
}
