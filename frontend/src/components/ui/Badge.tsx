import type { ReactNode } from "react";
import { badgeToneCls } from "./styles";

export type BadgeTone = keyof typeof badgeToneCls;

/**
 * Square-ish status label. `Chip` (rounded-full) is the older sibling used for
 * filters and counts; Badge is for a value's state in a table cell.
 */
export function Badge({
  tone = "gray",
  children,
}: {
  tone?: BadgeTone;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11.5px] font-medium ${badgeToneCls[tone]}`}
    >
      <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-current opacity-80" />
      {children}
    </span>
  );
}
