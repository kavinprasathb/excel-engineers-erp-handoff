import type { QuotationFormat } from "../../api/types";
import type { DraftLine } from "./draft";

export const OFFER_LAYOUTS: { value: QuotationFormat; letter: string; title: string; text: string }[] = [
  {
    value: "pump",
    letter: "A",
    title: "Pump Offer",
    text: "1–3 pumps: a datasheet, scope of supply and price for each pump.",
  },
  {
    value: "spares",
    letter: "B",
    title: "Spares & Service",
    text: "Parts grouped by pump model, with MOC / Part No columns and service charges.",
  },
  {
    value: "technical",
    letter: "C",
    title: "Technical Sheet",
    text: "4 or more pumps side by side, so the offer stays on 1–2 pages.",
  },
];

/**
 * The layout the app would pick: 4 or more items with technical data → the
 * sheet, a spares-type quotation → spares, otherwise the pump offer. Only a
 * suggestion; the user's choice always stands.
 */
export function suggestedLayout(type: string, lines: DraftLine[]): QuotationFormat {
  const items = lines.filter((l) => l.kind !== "note");
  if (items.length >= 4 && items.some((l) => Object.values(l.tech).some((v) => v.trim()))) return "technical";
  return type === "spares" ? "spares" : "pump";
}
