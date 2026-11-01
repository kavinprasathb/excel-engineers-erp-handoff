/**
 * Determinate when we know the total, indeterminate when we do not — an import
 * reports `total_rows: 0` until header detection finishes, and a bar that sat
 * at 0% would read as "stuck" rather than "counting".
 */
export interface ProgressBarProps {
  /** Omit for the indeterminate state. */
  value?: number;
  max?: number;
  label?: string;
}

export function ProgressBar({ value, max = 100, label }: ProgressBarProps) {
  const indeterminate = value === undefined || max <= 0;
  const pct = indeterminate ? 0 : Math.min(100, Math.max(0, (value / max) * 100));

  return (
    <div>
      {label ? (
        <div className="mb-1.5 flex items-center justify-between text-[12px] text-ink-2">
          <span>{label}</span>
          {indeterminate ? null : <span className="tabular-nums">{Math.round(pct)}%</span>}
        </div>
      ) : null}
      <div
        role="progressbar"
        aria-valuenow={indeterminate ? undefined : Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label ?? "Progress"}
        className="h-1.5 w-full overflow-hidden rounded-full bg-hoverfill"
      >
        {indeterminate ? (
          <div className="h-full w-1/3 animate-pulse rounded-full bg-brand" />
        ) : (
          <div className="h-full rounded-full bg-brand transition-[width]" style={{ width: `${pct}%` }} />
        )}
      </div>
    </div>
  );
}
