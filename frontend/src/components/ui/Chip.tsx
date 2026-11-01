import type { ReactNode } from "react";

const TONES = {
  green: "bg-green-bg text-green",
  red: "bg-red-bg text-red",
  amber: "bg-amber-bg text-amber",
  gray: "bg-hoverfill text-ink-2",
} as const;

export type ChipTone = keyof typeof TONES;

export function Chip({ tone, children }: { tone: ChipTone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}
