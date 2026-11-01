import type { ReactNode } from "react";

/**
 * Filters are a bare row, not a card.
 *
 * Wrapping them in a bordered panel gives the eye a second box to parse before
 * it reaches the data, and leaves a band of empty card whenever the controls do
 * not fill the width. The controls are already bordered; that is enough edge.
 */
export function FilterBar({
  children,
  label = "Filters",
}: {
  children: ReactNode;
  label?: string;
}) {
  return (
    <section aria-label={label} className="mb-3 flex flex-wrap items-center gap-2">
      {children}
    </section>
  );
}

/**
 * Toggles and the reset link. Pushed to the right of the same row on wide
 * screens so the row reads left-to-right as narrow-the-list then clear-it, and
 * dropping onto its own line only when there is genuinely no space.
 */
export function FilterExtras({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-center gap-2 sm:ml-auto">{children}</div>;
}
