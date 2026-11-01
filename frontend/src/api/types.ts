/**
 * Hand-written mirrors of `docs/api-contract.md`.
 *
 * TEMPORARY: these will be replaced by types generated from the backend's
 * OpenAPI schema (`openapi-typescript` is already a devDependency). Until the
 * backend is up and the schema is stable, hand-writing them keeps the frontend
 * unblocked. When you generate, delete this file rather than keeping both.
 */

export type Role = "admin" | "staff";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
}

export interface Settings {
  company_name: string;
  /** Server compares against this; the client never re-implements the rule. */
  low_stock_threshold: number;
  /** Basis points: 1800 === 18%. */
  default_gst_rate_bp: number;

  /**
   * The letterhead every printed document carries. It lives in settings rather
   * than in a template because it demonstrably changes — the company's 2020
   * offers carry a different phone number from its 2026 ones — and changing it
   * should be an admin editing a form, not a developer editing code.
   */
  company_address_line1: string;
  company_address_line2: string;
  company_city: string;
  company_state: string;
  company_pincode: string;
  company_gstin: string;
  company_phone: string;
  company_mobile: string;
  company_email: string;
  signatory_name: string;
  signatory_designation: string;
  quotation_terms_defaults: QuotationTermsDefaults;
  quotation_spec_defaults: SpecDefault[];
}

export type SettingsPatch = Partial<Settings>;

/** Every list endpoint returns this envelope. */
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Ref {
  id: number;
  name: string;
}

/** A branch named on a document: enough to show which one. */
export interface BranchRef {
  id: number;
  /** "CUST-0001-BR01": issued by the server, never edited. */
  code: string;
  name: string;
}

/**
 * An optional branch of a customer or supplier, with its own GST number and
 * address. Removing one only sets `is_active` false, so a document that named
 * it still prints it.
 */
export interface SupplierBranch extends BranchRef {
  gstin: string;
  emails: string[];
  phones: string[];
  address_line1: string;
  city: string;
  state: string;
  pincode: string;
  is_active: boolean;
}

export interface CustomerBranch extends SupplierBranch {
  contact_person: string;
  designation: string;
}

export type SupplierBranchInput = Omit<SupplierBranch, "id" | "code" | "is_active">;
export type CustomerBranchInput = Omit<CustomerBranch, "id" | "code" | "is_active">;

export interface Supplier {
  id: number;
  /** "SUP-0001": issued by the server, read-only. */
  code: string;
  name: string;
  contact_person: string;
  phone: string;
  email: string;
  /** Every email, first one first; `email` always equals the first. */
  emails: string[];
  /** Every phone number, first one first; `phone` always equals the first. */
  phones: string[];
  gstin: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  pincode: string;
  notes: string;
  is_active: boolean;
  product_count: number;
  branches: SupplierBranch[];
  /** Mandatory fields a record saved before they were mandatory still lacks. */
  missing_fields: string[];
}

export interface Category {
  id: number;
  name: string;
  product_count: number;
}

export interface ProductInventory {
  quantity_on_hand: number;
  quantity_reserved: number;
  /** Always from the server. The client must never subtract to derive this. */
  quantity_available: number;
}

/**
 * How a product is kept. stocked: on the shelf, with low-stock alerts.
 * to_order: quoted and bought in when an order needs it (0 stock is normal).
 * service: labour, transport, service charges; never stocked.
 */
export type StockType = "stocked" | "to_order" | "service";

export const STOCK_TYPES: readonly { value: StockType; label: string }[] = [
  { value: "to_order", label: "To order" },
  { value: "stocked", label: "Stocked" },
  { value: "service", label: "Service" },
];

export function stockTypeLabel(t: StockType | undefined): string {
  return STOCK_TYPES.find((x) => x.value === t)?.label ?? "Stocked";
}

export interface Product {
  id: number;
  sku: string;
  name: string;
  model_number: string;
  description: string;
  unit: string;
  hsn_code: string;
  /** Integer paise. */
  /** null when the viewer is staff: purchase cost is owner-only. */
  purchase_cost: number | null;
  /** Integer paise. */
  sell_price: number;
  gst_rate_bp: number;
  is_active: boolean;
  stock_type: StockType;
  supplier: Ref | null;
  category: Ref | null;
  inventory: ProductInventory;
}

export type StockStatus = "all" | "low" | "out" | "ok";

export interface InventoryRow {
  product_id: number;
  sku: string;
  name: string;
  model_number: string;
  unit: string;
  supplier: Ref | null;
  category: Ref | null;
  quantity_on_hand: number;
  quantity_reserved: number;
  quantity_available: number;
  /** Computed server-side against the settings threshold. */
  is_low_stock: boolean;
  is_out_of_stock: boolean;
  /** Always sent by the server; "stocked" when absent. */
  stock_type?: StockType;
}

export interface InventorySummary {
  total_products: number;
  low_stock_count: number;
  out_of_stock_count: number;
  missing_supplier_count: number;
  total_stock_value_paise: number | null;
}

// Mirrors app/constants.py MovementType exactly. "issue" does not exist;
// goods leaving on a challan are "deliver", and a spreadsheet-set opening
// balance is "import".
export type MovementType =
  | "adjust"
  | "receive"
  | "reserve"
  | "release"
  | "deliver"
  | "import";

export type ReferenceType =
  | "manual"
  | "import"
  | "order"
  | "purchase_order"
  | "challan";

export interface Movement {
  id: number;
  movement_type: MovementType;
  on_hand_delta: number;
  reserved_delta: number;
  quantity_on_hand_after: number;
  quantity_reserved_after: number;
  reference_type: string;
  reference_id: number | null;
  note: string;
  created_by: { id: number; full_name: string } | null;
  created_at: string;
}

export type ImportStatus = "pending" | "running" | "completed" | "failed";

export interface ImportRowError {
  row: number;
  column: string;
  message: string;
  value: string;
}

export interface ImportJob {
  id: string;
  status: ImportStatus;
  filename: string;
  /** 0 until header detection finishes — the progress bar is indeterminate then. */
  total_rows: number;
  processed_rows: number;
  created_count: number;
  updated_count: number;
  skipped_count: number;
  error_count: number;
  /** Capped at 200 entries; `error_count` is the true total. */
  errors: ImportRowError[];
  column_mapping: Record<string, number>;
  unmapped_headers: string[];
  header_row_index: number;
  message: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface Health {
  status: string;
  db: string;
  version: string;
}

/** The error envelope every non-2xx response carries. */
export type ApiErrorCode =
  | "not_found"
  | "conflict"
  | "insufficient_stock"
  | "insufficient_reservation"
  | "validation_error"
  | "invalid_credentials"
  | "not_authenticated"
  | "rate_limited";

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export interface LoginBody {
  email: string;
  password: string;
}

export interface ChangePasswordBody {
  current_password: string;
  new_password: string;
}

// ---------------------------------------------------------------------------
// Customers
// ---------------------------------------------------------------------------

/**
 * Deliberately the same shape as Supplier. They are the same kind of record
 * pointed the other way, and two divergent address models would mean two of
 * every form, validator and formatter.
 *
 * Blank shipping fields mean "same as billing". Nothing copies one into the
 * other — not the API, not the PDF, not the form.
 */
export interface Customer {
  id: number;
  /** "CUST-0001": issued by the server, read-only. */
  code: string;
  name: string;
  contact_person: string;
  designation: string;
  phone: string;
  email: string;
  /** Every email, first one first; `email` always equals the first. */
  emails: string[];
  /** Every phone number, first one first; `phone` always equals the first. */
  phones: string[];
  gstin: string;
  billing_address_line1: string;
  billing_address_line2: string;
  billing_city: string;
  billing_state: string;
  billing_pincode: string;
  shipping_address_line1: string;
  shipping_address_line2: string;
  shipping_city: string;
  shipping_state: string;
  shipping_pincode: string;
  notes: string;
  is_active: boolean;
  branches: CustomerBranch[];
  /** Mandatory fields a record saved before they were mandatory still lacks. */
  missing_fields: string[];
}

export type CustomerCreate = Omit<Customer, "id" | "code" | "branches" | "missing_fields">;
export type CustomerPatch = Partial<CustomerCreate>;

// ---------------------------------------------------------------------------
// Customer / supplier import
// ---------------------------------------------------------------------------

/** One proposed record from `POST /{customers|suppliers}/import/preview`. */
export interface ImportPreviewRecord<T> {
  data: T;
  warnings: string[];
  duplicate_of: Ref | null;
}

export interface ImportPreview<T> {
  records: ImportPreviewRecord<T>[];
  /** More than 2,000 records were found; only the first 2,000 came back. */
  truncated: boolean;
}

export interface ImportCommitResult {
  created: number;
}

// ---------------------------------------------------------------------------
// Product lookup
// ---------------------------------------------------------------------------

/** What an item picker needs from the catalogue, and nothing more. */
export interface ProductLookup {
  id: number;
  sku: string;
  name: string;
  model_number: string;
  unit: string;
  hsn_code: string;
  /** The list price. `purchase_cost` never reaches a customer-facing screen. */
  sell_price: number;
  quantity_available: number;
  /** Always sent by the server; "stocked" when absent. */
  stock_type?: StockType;
}

// ---------------------------------------------------------------------------
// Quotations
// ---------------------------------------------------------------------------

export type QuotationType = "pumps" | "valves" | "spares";
export type QuotationStatus = "pending" | "accepted" | "declined" | "superseded";
export type LineKind = "product" | "note";

export const QUOTATION_TYPES: readonly { value: QuotationType; label: string; prefix: string }[] = [
  { value: "pumps", label: "Pumps", prefix: "ESQP" },
  { value: "valves", label: "Valves", prefix: "ESQV" },
  { value: "spares", label: "Spares", prefix: "ESQSP" },
];

export const QUOTATION_STATUSES: readonly QuotationStatus[] = [
  "pending",
  "accepted",
  "declined",
  "superseded",
];

export interface QuotationLine {
  id: number;
  position: number;
  kind: LineKind;
  /** Printed beside the quantity: "Each", "Set". */
  unit_label: string;
  /** HSN (goods) or SAC (services) code; "" when not given. */
  hsn_code: string;
  /** null for a free-text line. */
  product_id: number | null;
  description: string;
  quantity: number;
  rate_paise: number;
  value_paise: number;
  /** The item's technical deviation rows; only filled ones print, under the item. */
  deviations: QuotationDeviation[];
  /** A multi-item line's items; empty for an ordinary line. */
  components: QuotationComponent[];
  /** Technical format: the column heading ("UF Feed"). */
  service: string;
  /** Technical format: one value per row of the quotation's tech_rows. */
  tech_values: string[];
  /** Spares layout columns. */
  part_no: string;
  moc: string;
  delivery: string;
  /** Pump layout: what the price includes. */
  supply_scope: string;
}

/**
 * How the offer letter is laid out; the data is the same for all three.
 * pump: datasheet and price line per pump. spares: tables per pump model,
 * service at the end. technical: pumps side by side.
 */
export type QuotationFormat = "pump" | "spares" | "technical";

/** Spares layout: optional columns that print when switched on. */
export type PrintColumn = "part_no" | "moc" | "unit" | "delivery";

/** One row of the technical offer sheet. */
export interface TechRow {
  section: string;
  label: string;
}

export interface QuotationTerm {
  id: number;
  position: number;
  label: string;
  text: string;
  included: boolean;
}

export interface QuotationLineIn {
  kind: LineKind;
  unit_label: string;
  hsn_code: string;
  product_id: number | null;
  description: string;
  quantity: number;
  rate_paise: number;
  /** Omitted: the server copies the default rows. A note has none. */
  deviations?: QuotationDeviation[];
  /** A multi-item line's items, by inventory id; empty for an ordinary line. */
  components?: QuotationComponent[];
  service?: string;
  tech_values?: string[];
  part_no?: string;
  moc?: string;
  delivery?: string;
  supply_scope?: string;
}

export interface QuotationTermIn {
  label: string;
  text: string;
  included: boolean;
}

/**
 * One inventory item of a multi-item line (a pump set), and how many of it
 * go into one unit of the line. Stock moves per item, never by the line's text.
 */
export interface QuotationComponent {
  product_id: number;
  name: string;
  quantity: number;
}

/** Something quoted before that matches a description being typed. */
export interface ItemSuggestion {
  description: string;
  details: string;
  part_no: string;
  moc: string;
  unit: string;
  rate_paise: number;
  hsn_code: string;
  offer_no: string;
  offer_date: string | null;
  customer_name: string;
  /** Quoted to the customer of the quotation being written. */
  same_customer: boolean;
  /** "past offer" (the client's letters) or "quotation" (made in the app). */
  source: string;
}

/** One `label : value` row of an item's technical deviation. */
export interface QuotationDeviation {
  label: string;
  value: string;
}

/** A list row. */
/**
 * Which list a quotation number is on, by its latest version: the original
 * quotation, a revised quotation (R1, R2...: product or technical changes),
 * or a negotiation (N1, N2...: price only).
 */
export type QuotationStage = "quotation" | "revised" | "negotiation";

/** What a new version is for: a revised quotation, or a price negotiation. */
export type VersionKind = "revision" | "negotiation";

export interface QuotationSummary {
  id: number;
  number: string;
  type: QuotationType;
  /** Position in the number's history: 0 is the original, then 1, 2... */
  revision: number;
  /** R of the revised quotation this version belongs to; 0 is the original. */
  rev_no: number;
  /** N of its negotiation round; 0 is not a negotiation. */
  neg_no: number;
  /** The original quotation's number, e.g. ESQSP-26-70. */
  base_number: string;
  /** "Initial quote", "Revision R2", "Negotiation N1", "Revision R2 · Negotiation N1". */
  stage_label: string;
  format: QuotationFormat;
  /** When this version was made. */
  created_at: string;
  customer: Ref;
  quote_date: string;
  subject: string;
  status: QuotationStatus;
  total_paise: number;
  updated_at: string;
}

export interface Quotation extends QuotationSummary {
  /** The customer's branch it is addressed to; null is the head office. */
  customer_branch: BranchRef | null;
  reference: string;
  notes: string;
  /** Set only when declined; mandatory then. */
  decline_reason: string;
  supersedes_id: number | null;
  /** Only the highest revision of a number may be edited or decided. */
  is_latest: boolean;
  print_columns: PrintColumn[];
  tech_rows: TechRow[];
  /** Technical format: the scope of supply. */
  scope: string;
  /** Technical sheet: what the unit price covers. */
  price_label: string;
  lines: QuotationLine[];
  terms: QuotationTerm[];
  created_at: string;
}

export interface QuotationCreate {
  type: QuotationType;
  customer_id: number;
  customer_branch_id?: number | null;
  quote_date: string;
  subject: string;
  reference: string;
  notes?: string;
  format?: QuotationFormat;
  print_columns?: PrintColumn[];
  tech_rows?: TechRow[];
  scope?: string;
  price_label?: string;
  lines: QuotationLineIn[];
  /** Omitted: the server copies the defaults for the type. */
  terms?: QuotationTermIn[];
}

export interface QuotationPatch {
  customer_id?: number;
  customer_branch_id?: number | null;
  quote_date?: string;
  subject?: string;
  reference?: string;
  notes?: string;
  format?: QuotationFormat;
  print_columns?: PrintColumn[];
  tech_rows?: TechRow[];
  scope?: string;
  price_label?: string;
  lines?: QuotationLineIn[];
  terms?: QuotationTermIn[];
}

/** Two versions of one number side by side: what changed from one to the other. */
export interface QuotationCompare {
  changes: QuotationChange[];
  lines: QuotationLineChange[];
}

/** One thing a negotiation changed against the version it was copied from. */
export interface QuotationChange {
  section: string;
  item: string;
  field: string;
  before: string;
  after: string;
}

/** One item compared with the version the negotiation was started from. */
export interface QuotationLineChange {
  description: string;
  old_quantity: number | null;
  new_quantity: number | null;
  old_rate_paise: number | null;
  new_rate_paise: number | null;
  change: "kept" | "added" | "removed";
}

export type DashboardStage = "awaiting" | "negotiating" | "accepted" | "declined";

export interface DashboardRow {
  id: number;
  number: string;
  customer: string;
  /** 0 = initial quote, n = the nth version after it. */
  stage: number;
  stage_label: string;
  status: QuotationStatus;
  quote_date: string;
  updated_at: string;
  total_paise: number;
  decline_reason: string;
}

export interface QuotationDashboard {
  buckets: Record<DashboardStage, { count: number; total_paise: number }>;
  awaiting: DashboardRow[];
  negotiating: DashboardRow[];
  accepted: DashboardRow[];
  declined: DashboardRow[];
}

export interface TermDefault {
  label: string;
  text: string;
}
export type QuotationTermsDefaults = Record<QuotationType, TermDefault[]>;

export interface SpecDefault {
  label: string;
  value: string;
}
