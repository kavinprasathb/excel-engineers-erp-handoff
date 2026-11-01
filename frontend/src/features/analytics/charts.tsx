import { useState } from "react";
import type { ReactNode } from "react";

export interface Slice {
  label: string;
  value: number;
  color: string;
  /** Shown beside the label in the legend and the tooltip, e.g. "₹71,687". */
  detail?: string;
}

/**
 * A donut: the share of each slice, a headline in the middle, and a legend
 * that names every slice with its number, so colour is never the only clue.
 * Hovering a slice or its legend row highlights it.
 */
export function Donut({
  slices,
  center,
  sub,
  showValue = true,
}: {
  slices: Slice[];
  center: ReactNode;
  sub?: string;
  /** False when `detail` already says the amount, e.g. money charts. */
  showValue?: boolean;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const total = slices.reduce((s, x) => s + x.value, 0);
  const r = 70;
  const stroke = 14;
  const c = 2 * Math.PI * r;
  // A 2px surface gap between slices, only when there is more than one.
  const shown = slices.filter((s) => s.value > 0);
  // Room for the rounded caps plus a visible gap between segments.
  const gap = shown.length > 1 ? stroke + 6 : 0;
  let offset = 0;

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center">
      <svg viewBox="0 0 180 180" className="h-44 w-44 shrink-0" role="img" aria-label={slices.map((s) => `${s.label} ${s.value}`).join(", ")}>
        <circle cx="90" cy="90" r={r} fill="none" stroke="var(--color-hoverfill)" strokeWidth={stroke} />
        {total > 0
          ? slices.map((s, i) => {
              if (s.value <= 0) return null;
              const len = (s.value / total) * c;
              const dash = Math.max(len - gap, 0.01);
              const el = (
                <circle
                  key={s.label}
                  cx="90"
                  cy="90"
                  r={r}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={hover === i ? stroke + 4 : stroke}
                  strokeLinecap="round"
                  strokeDasharray={`${dash} ${c - dash}`}
                  strokeDashoffset={-(offset + (shown.length > 1 ? gap / 2 : 0))}
                  transform="rotate(-90 90 90)"
                  opacity={hover === null || hover === i ? 1 : 0.35}
                  onMouseEnter={() => setHover(i)}
                  onMouseLeave={() => setHover(null)}
                  className="cursor-pointer transition-all"
                >
                  <title>{`${s.label}: ${s.value} (${Math.round((s.value / total) * 100)}%)${s.detail ? ` · ${s.detail}` : ""}`}</title>
                </circle>
              );
              offset += len;
              return el;
            })
          : null}
        <foreignObject x="30" y="55" width="120" height="70">
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="text-[26px] font-medium tracking-tight tabular-nums text-ink">{center}</div>
            {sub ? <div className="text-[11px] text-ink-2">{sub}</div> : null}
          </div>
        </foreignObject>
      </svg>
      <ul className="w-full min-w-0 space-y-1.5 text-[13px]">
        {slices.map((s, i) => (
          <li
            key={s.label}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            className={`flex items-center gap-2 rounded-md px-1.5 py-1 ${hover === i ? "bg-hoverfill" : ""}`}
          >
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: s.color }} />
            <span className="min-w-0 flex-1 truncate text-ink">{s.label}</span>
            {showValue ? <span className="tabular-nums font-medium text-ink">{s.value}</span> : null}
            <span className="w-10 text-right tabular-nums text-ink-2">
              {total ? `${Math.round((s.value / total) * 100)}%` : "—"}
            </span>
            {s.detail ? <span className="hidden tabular-nums text-ink-2 sm:inline">{s.detail}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Vertical columns, one per month, with the value on hover and a label on the tallest. */
export function Columns({
  data,
  format,
  color = "#8b7cf0",
}: {
  data: { label: string; value: number; note?: string }[];
  format: (v: number) => string;
  color?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(0, ...data.map((d) => d.value));
  const top = data.findIndex((d) => d.value === max);
  return (
    <div>
      <div className="relative flex h-48 items-end gap-3">
        {data.map((d, i) => {
          const h = max > 0 ? Math.max((d.value / max) * 100, d.value > 0 ? 2 : 0) : 0;
          return (
            <div
              key={d.label}
              className="relative flex h-full min-w-0 flex-1 items-end justify-center rounded-lg bg-hoverfill"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            >
              {hover === i || (hover === null && i === top && max > 0) ? (
                <div className="pointer-events-none absolute z-10 whitespace-nowrap rounded-md border border-line bg-card px-2 py-1 text-[12px] shadow-sm" style={{ bottom: `calc(${h}% + 6px)` }}>
                  <span className="font-medium tabular-nums text-ink">{format(d.value)}</span>
                  {d.note ? <span className="text-ink-2"> · {d.note}</span> : null}
                </div>
              ) : null}
              <div
                className="w-full rounded-lg transition-opacity"
                style={{
                  height: `${h}%`,
                  background: `repeating-linear-gradient(90deg, rgba(255,255,255,0.35) 0 1px, transparent 1px 3px), linear-gradient(180deg, color-mix(in srgb, ${color} 75%, white), ${color})`,
                  opacity: hover === null || hover === i ? 1 : 0.55,
                }}
              />
            </div>
          );
        })}
      </div>
      <div className="mt-1.5 flex gap-2">
        {data.map((d) => (
          <div key={d.label} className="min-w-0 flex-1 truncate text-center text-[11px] text-ink-2">
            {d.label}
          </div>
        ))}
      </div>
    </div>
  );
}
