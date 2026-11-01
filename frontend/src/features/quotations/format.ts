import type { QuotationStage, QuotationStatus, QuotationType } from "../../api/types";
import { QUOTATION_TYPES } from "../../api/types";

export function typeLabel(type: QuotationType): string {
  return QUOTATION_TYPES.find((t) => t.value === type)?.label ?? type;
}

/** The client's word for a version: "Initial quote", "Revision R2", "Negotiation N1"... */
export function stageLabel(v: { rev_no: number; neg_no: number }): string {
  const parts = [];
  if (v.rev_no) parts.push(`Revision R${v.rev_no}`);
  if (v.neg_no) parts.push(`Negotiation N${v.neg_no}`);
  return parts.join(" · ") || "Initial quote";
}

/** Which list a version belongs on, and the path of that list. */
export function stageOf(v: { rev_no: number; neg_no: number }): QuotationStage {
  return v.neg_no ? "negotiation" : v.rev_no ? "revised" : "quotation";
}

export const STAGE_PATH: Record<QuotationStage, string> = {
  quotation: "/quotations",
  revised: "/revised-quotations",
  negotiation: "/negotiations",
};

/** dd.mm.yyyy — the way the letter prints it. */
export function formatQuoteDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return d && m && y ? `${d}.${m}.${y}` : iso;
}

/** Whole rupees with Indian grouping; the letter prints no paise. */
export function formatRupees(paise: number): string {
  return `₹${Math.round(paise / 100).toLocaleString("en-IN")}`;
}

/** Plain words for the customer-facing statuses. "Superseded" is jargon; "Old version" is what it means. */
export const STATUS_LABEL: Record<QuotationStatus, string> = {
  pending: "Pending",
  accepted: "Accepted",
  declined: "Declined",
  superseded: "Old version",
};
