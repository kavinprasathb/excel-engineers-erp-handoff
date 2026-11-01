import type {
  LineKind,
  Quotation,
  QuotationCreate,
  QuotationDeviation,
  PrintColumn,
  QuotationFormat,
  QuotationLineIn,
  QuotationPatch,
  QuotationTermIn,
  QuotationType,
} from "../../api/types";

/**
 * The editor's working copy. Money and quantity are kept as the strings the
 * user typed so a half-entered "14" does not snap to "14.00" under the caret;
 * they are parsed once, on save.
 */
export interface DraftLine {
  key: string;
  /** A note is a free text row between products ("KSB Make"). */
  kind: LineKind;
  unit_label: string;
  hsn_code: string;
  product_id: number | null;
  /** Shown as a small chip so the user knows the line came from the catalogue. */
  sku: string;
  description: string;
  quantity: string;
  rate: string;
  /** The item's technical deviation rows. Filled ones print under the item. */
  deviations: DraftSpec[];
  /** A multi-item line's items, by inventory id; stock moves per item, never by the text. */
  components: DraftComponent[];
  /** What the last Finalise Description wrote ("" if none). Text that differs is the user's own. */
  finalisedText: string;
  /** Selling price of the catalogue product, in paise, when it was picked. */
  price?: number;
  /** Technical format: the column heading ("UF Feed"). */
  service: string;
  /** Technical format: the value of each row, by the row's key. */
  tech: Record<string, string>;
  /** Spares layout columns; empty when not used. */
  part_no?: string;
  moc?: string;
  delivery?: string;
  /** Pump layout: what the price includes. */
  supply_scope?: string;
}

/** One row of the technical sheet; values live on the lines, by this key. */
export interface DraftTechRow {
  key: string;
  section: string;
  label: string;
}

export interface DraftComponent {
  product_id: number;
  name: string;
  /** How many go into one unit of the line, as typed. */
  quantity: string;
  /** In stock when it was picked; unknown for items loaded from a saved quote. */
  available?: number;
  /** Selling price of one, in paise, when it was picked; unknown for items of a saved quote. */
  price?: number;
}

export interface DraftTerm {
  key: string;
  label: string;
  text: string;
  included: boolean;
}

export interface DraftSpec {
  key: string;
  label: string;
  value: string;
}

export interface Draft {
  type: QuotationType;
  customer_id: string;
  /** "" is the head office; else one of the customer's branch ids. */
  customer_branch_id: string;
  quote_date: string;
  subject: string;
  reference: string;
  notes: string;
  format: QuotationFormat;
  /** Spares layout: optional columns that print. */
  print_columns: PrintColumn[];
  tech_rows: DraftTechRow[];
  scope: string;
  /** Technical sheet: what the unit price covers. */
  price_label: string;
  lines: DraftLine[];
  terms: DraftTerm[];
}

export type DraftErrors = Partial<
  Record<"customer_id" | "quote_date" | "lines" | "form", string>
> & { line?: Record<string, string> };

/** "Pump, Pump Base Frame, Coupling": what Finalise Description puts in the description. */
export function joinedNames(components: readonly { name: string }[]): string {
  return components.map((c) => c.name.trim()).filter(Boolean).join(", ");
}

let counter = 0;
export function nextKey(): string {
  counter += 1;
  return `k${counter}`;
}

function today(): string {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

export function emptyDraft(): Draft {
  return {
    type: "spares",
    customer_id: "",
    customer_branch_id: "",
    quote_date: today(),
    subject: "",
    reference: "",
    notes: "",
    format: "pump",
    print_columns: ["moc", "unit"],
    tech_rows: [],
    scope: "",
    price_label: "",
    lines: [],
    terms: [],
  };
}

/** The default technical deviation rows (from Settings) as fresh draft rows. */
export function deviationRows(defaults: readonly QuotationDeviation[] = []): DraftSpec[] {
  return defaults.map((d) => ({ key: nextKey(), label: d.label, value: d.value }));
}

export function emptyLine(defaults: readonly QuotationDeviation[] = []): DraftLine {
  return {
    key: nextKey(),
    kind: "product",
    unit_label: "Each",
    hsn_code: "",
    product_id: null,
    sku: "",
    description: "",
    quantity: "1",
    rate: "",
    deviations: deviationRows(defaults),
    components: [],
    finalisedText: "",
    service: "",
    tech: {},
  };
}

export function emptyNote(): DraftLine {
  return { ...emptyLine(), kind: "note", deviations: [] };
}

export function emptySpec(): DraftSpec {
  return { key: nextKey(), label: "", value: "" };
}

export function draftFrom(q: Quotation, skuOf: (productId: number) => string = () => ""): Draft {
  const rows = (q.tech_rows ?? []).map((r) => ({ key: nextKey(), section: r.section, label: r.label }));
  return {
    format: q.format ?? "pump",
    print_columns: q.print_columns ?? ["moc", "unit"],
    tech_rows: rows,
    scope: q.scope ?? "",
    price_label: q.price_label ?? "",
    type: q.type,
    customer_id: String(q.customer.id),
    customer_branch_id: q.customer_branch ? String(q.customer_branch.id) : "",
    quote_date: q.quote_date,
    subject: q.subject,
    reference: q.reference,
    notes: q.notes,
    lines: q.lines.map((l) => ({
      key: nextKey(),
      kind: l.kind,
      unit_label: l.unit_label,
      hsn_code: l.hsn_code,
      product_id: l.product_id,
      sku: l.product_id === null ? "" : skuOf(l.product_id),
      description: l.description,
      quantity: String(l.quantity),
      rate: rupeesFromPaise(l.rate_paise),
      deviations: deviationRows(l.deviations),
      components: l.components.map((c) => ({
        product_id: c.product_id,
        name: c.name,
        quantity: String(c.quantity),
      })),
      // A saved set counts as finalised; whatever the box says is kept as is.
      finalisedText: joinedNames(l.components),
      service: l.service ?? "",
      tech: Object.fromEntries(rows.map((r, i) => [r.key, l.tech_values?.[i] ?? ""])),
      part_no: l.part_no ?? "",
      moc: l.moc ?? "",
      delivery: l.delivery ?? "",
      supply_scope: l.supply_scope ?? "",
    })),
    terms: q.terms.map((t) => ({
      key: nextKey(),
      label: t.label,
      text: t.text,
      included: t.included,
    })),
  };
}

/** Whole rupees when there are no paise, else two decimals — never "14760.00". */
export function rupeesFromPaise(paise: number): string {
  return paise % 100 === 0 ? String(paise / 100) : (paise / 100).toFixed(2);
}

export function paiseFromRupees(text: string): number {
  return Math.round(Number(text.replace(/,/g, "")) * 100);
}

export function lineValuePaise(line: DraftLine): number {
  if (line.kind === "note") return 0;
  const qty = Number(line.quantity);
  const rate = paiseFromRupees(line.rate);
  if (!Number.isFinite(qty) || !Number.isFinite(rate)) return 0;
  return Math.round(qty) * rate;
}

export function draftTotalPaise(draft: Draft): number {
  return draft.lines.reduce((sum, l) => sum + lineValuePaise(l), 0);
}

export function validate(draft: Draft): DraftErrors {
  const errors: DraftErrors = {};
  if (!draft.customer_id) errors.customer_id = "Pick the customer this offer is addressed to.";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(draft.quote_date)) errors.quote_date = "Enter a date.";
  if (!draft.lines.some((l) => l.kind === "product")) errors.lines = "Add at least one item.";
  const line: Record<string, string> = {};
  for (const l of draft.lines) {
    if (!l.description.trim()) line[l.key] = l.kind === "note" ? "Type the note." : "Describe the item.";
    else if (l.kind === "note") continue;
    else if (!Number.isInteger(Number(l.quantity)) || Number(l.quantity) <= 0)
      line[l.key] = "Quantity must be a whole number above zero.";
    else if (l.rate.trim() === "" || !Number.isFinite(Number(l.rate.replace(/,/g, ""))))
      line[l.key] = "Enter a rate in rupees.";
    else if (paiseFromRupees(l.rate) < 0) line[l.key] = "A rate cannot be negative.";
    else if (l.components.some((c) => !Number.isInteger(Number(c.quantity)) || Number(c.quantity) <= 0))
      line[l.key] = "Each item needs a whole-number quantity above zero.";
  }
  if (Object.keys(line).length > 0) errors.line = line;
  return errors;
}

function sheetOut(draft: Draft) {
  return {
    format: draft.format,
    print_columns: draft.print_columns,
    tech_rows: draft.tech_rows
      .filter((r) => r.label.trim() !== "")
      .map((r) => ({ section: r.section.trim(), label: r.label.trim() })),
    scope: draft.scope.trim(),
    price_label: draft.price_label.trim(),
  };
}

function linesOut(draft: Draft): QuotationLineIn[] {
  const rows = draft.tech_rows.filter((r) => r.label.trim() !== "");
  return draft.lines.map((l) =>
    l.kind === "note"
      ? {
          kind: "note",
          unit_label: "",
          hsn_code: "",
          product_id: null,
          description: l.description.trim(),
          quantity: 1,
          rate_paise: 0,
          deviations: [],
          components: [],
        }
      : {
          kind: "product",
          unit_label: l.unit_label.trim() || "Each",
          hsn_code: l.hsn_code.trim(),
          // A multi-item line has no single product: its items carry them.
          product_id: l.components.length ? null : l.product_id,
          description: l.description.trim(),
          quantity: Math.round(Number(l.quantity)),
          rate_paise: paiseFromRupees(l.rate),
          deviations: l.deviations
            .filter((d) => d.label.trim() !== "")
            .map((d) => ({ label: d.label.trim(), value: d.value.trim() })),
          components: l.components.map((c) => ({
            product_id: c.product_id,
            name: c.name,
            quantity: Math.round(Number(c.quantity)),
          })),
          service: l.service.trim(),
          // The pump offer and the technical sheet share the datasheet rows.
          tech_values: draft.format === "spares" ? [] : rows.map((r) => (l.tech[r.key] ?? "").trim()),
          part_no: (l.part_no ?? "").trim(),
          moc: (l.moc ?? "").trim(),
          delivery: (l.delivery ?? "").trim(),
          supply_scope: (l.supply_scope ?? "").trim(),
        },
  );
}

function termsOut(draft: Draft): QuotationTermIn[] {
  return draft.terms
    .filter((t) => t.label.trim() !== "")
    .map((t) => ({ label: t.label.trim(), text: t.text.trim(), included: t.included }));
}

export function toCreate(draft: Draft, useDefaultTerms: boolean): QuotationCreate {
  return {
    type: draft.type,
    customer_id: Number(draft.customer_id),
    customer_branch_id: draft.customer_branch_id ? Number(draft.customer_branch_id) : null,
    quote_date: draft.quote_date,
    subject: draft.subject.trim(),
    reference: draft.reference.trim(),
    notes: draft.notes,
    ...sheetOut(draft),
    lines: linesOut(draft),
    ...(useDefaultTerms ? {} : { terms: termsOut(draft) }),
  };
}

export function toPatch(draft: Draft): QuotationPatch {
  return {
    customer_id: Number(draft.customer_id),
    customer_branch_id: draft.customer_branch_id ? Number(draft.customer_branch_id) : null,
    quote_date: draft.quote_date,
    subject: draft.subject.trim(),
    reference: draft.reference.trim(),
    notes: draft.notes,
    ...sheetOut(draft),
    lines: linesOut(draft),
    terms: termsOut(draft),
  };
}
