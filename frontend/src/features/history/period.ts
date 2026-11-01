/**
 * Named periods for Quote History, resolved to from/to dates (inclusive,
 * yyyy-mm-dd, local time). "custom" leaves the dates to the user.
 */
export type Period =
  | "all"
  | "this-month"
  | "last-month"
  | "last-3-months"
  | "last-6-months"
  | "this-year"
  | "last-year"
  | "custom";

export const PERIODS: readonly { value: Period; label: string }[] = [
  { value: "all", label: "All time" },
  { value: "this-month", label: "This month" },
  { value: "last-month", label: "Last month" },
  { value: "last-3-months", label: "Last 3 months" },
  { value: "last-6-months", label: "Last 6 months" },
  { value: "this-year", label: "This year" },
  { value: "last-year", label: "Last year" },
  { value: "custom", label: "Custom dates…" },
];

function iso(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

/** The from/to a named period means today. `today` is injectable for tests. */
export function periodRange(p: Period, today = new Date()): { from: string; to: string } {
  const y = today.getFullYear();
  const m = today.getMonth();
  switch (p) {
    case "this-month":
      return { from: iso(new Date(y, m, 1)), to: iso(new Date(y, m + 1, 0)) };
    case "last-month":
      return { from: iso(new Date(y, m - 1, 1)), to: iso(new Date(y, m, 0)) };
    // "Last 3 months" = this month and the two before it, whole months.
    case "last-3-months":
      return { from: iso(new Date(y, m - 2, 1)), to: iso(new Date(y, m + 1, 0)) };
    case "last-6-months":
      return { from: iso(new Date(y, m - 5, 1)), to: iso(new Date(y, m + 1, 0)) };
    case "this-year":
      return { from: `${y}-01-01`, to: `${y}-12-31` };
    case "last-year":
      return { from: `${y - 1}-01-01`, to: `${y - 1}-12-31` };
    default:
      return { from: "", to: "" };
  }
}

/** dd.mm.yyyy for the label beside the picker. */
export function shortDate(isoDate: string): string {
  const [y, m, d] = isoDate.split("-");
  return d && m && y ? `${d}.${m}.${y}` : isoDate;
}
