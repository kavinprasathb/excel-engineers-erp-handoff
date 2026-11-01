/**
 * Formatting helpers. Numbers are Indian-formatted throughout, and money only
 * ever arrives as an integer of paise — rendering it goes through here so a
 * float never gets introduced halfway down a component tree.
 */

/** Money from integer paise. `₹42,500.00`. */
export function formatMoney(paise: number): string {
  const rupees = paise / 100;
  return `₹${rupees.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatNumber(n: number): string {
  return n.toLocaleString("en-IN");
}

/** Missing data renders an em dash — never a fabricated 0. */
export const EMPTY = "—";

export function orDash(v: string | number | null | undefined): string {
  if (v === null || v === undefined || v === "") return EMPTY;
  return typeof v === "number" ? formatNumber(v) : v;
}

/** Server sends ISO-8601 UTC; the browser renders IST. */
export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return EMPTY;
  return d.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

/** GST is stored in basis points (1800 = 18%). Converted only at the edge. */
export function bpToPercent(bp: number): number {
  return bp / 100;
}

export function percentToBp(pct: number): number {
  return Math.round(pct * 100);
}

/** Paise to a plain rupee string for an editable field — no symbol, no grouping. */
export function paiseToRupeeInput(paise: number): string {
  return (paise / 100).toFixed(2);
}

/** Rupees as typed back to integer paise. Rounds, so 0.1 + 0.2 never leaks. */
export function rupeeInputToPaise(rupees: string): number {
  return Math.round(Number(rupees) * 100);
}
