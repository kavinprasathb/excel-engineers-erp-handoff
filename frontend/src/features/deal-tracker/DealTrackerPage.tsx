import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { Select } from "../../components/ui/Select";
import { Input } from "../../components/ui/Input";
import { Button } from "../../components/ui/Button";
import { Loading } from "../../components/ui/Spinner";
import { ErrorState } from "../../components/ui/ErrorState";
import { EmptyState } from "../../components/ui/EmptyState";
import { SearchInput } from "../../components/common/SearchInput";
import { FilterBar, FilterExtras } from "../../components/common/FilterBar";
import { cardCls, eyebrowCls } from "../../components/ui/styles";
import { api } from "../../api/client";
import { useListParams } from "../../lib/useListParams";
import { formatQuoteDate, formatRupees } from "../quotations/format";
import { PERIODS, periodRange } from "../history/period";
import type { Period } from "../history/period";

interface DealRow {
  /** The latest (or accepted) version: the one the deal stands on. */
  quotation_id: number;
  /** The original quotation. */
  original_id: number;
  customer: string;
  /** The original quotation's number. */
  quote_no: string;
  final_version: string;
  /** The latest revised quotation, e.g. ESQSP-26-7-R2; "" if never revised. */
  revision_ref: string;
  /** The latest negotiation, e.g. ESQSP-26-7-R2N1; "" if not in negotiation. */
  negotiation_ref: string;
  /** "Original → R1 → R2 → R2N1". */
  history: string;
  quote_date: string;
  description: string;
  quantity: number;
  quoted_paise: number;
  /** The latest revised quotation's price, before negotiation; null if never revised. */
  revised_paise: number | null;
  final_paise: number;
  discount_paise: number;
  value_paise: number;
  revisions: number;
  negotiations: number;
  result: string;
  decline_reason: string;
  accepted_on: string | null;
  order_id: number | null;
  order_no: string;
  from_stock: number | null;
  bought_in: number | null;
  po_id: number | null;
  po_no: string;
  supplier: string;
  po_date: string | null;
  po_sent: string | null;
  goods_received: string | null;
  delivered_on: string | null;
  days_to_deliver: number | null;
  stage: Stage;
}

type Stage =
  | "Quoted"
  | "Revised quotation"
  | "In negotiation"
  | "Declined"
  | "Waiting for stock"
  | "Ready to deliver"
  | "Delivered";

const STAGES: readonly { stage: Stage; color: string }[] = [
  { stage: "Quoted", color: "#8b7cf0" },
  { stage: "Revised quotation", color: "#5fb7d9" },
  { stage: "In negotiation", color: "#f6c453" },
  { stage: "Waiting for stock", color: "#f29ac8" },
  { stage: "Ready to deliver", color: "#7d86e8" },
  { stage: "Delivered", color: "#6fcf97" },
  { stage: "Declined", color: "#f29a9a" },
];
const COLOR = Object.fromEntries(STAGES.map((s) => [s.stage, s.color])) as Record<Stage, string>;
const KEYS = ["q", "stage", "period", "from", "to"] as const;

const d = (v: string | null) => (v ? formatQuoteDate(v) : "—");
const n = (v: number | null) => (v === null ? "—" : String(v));

/**
 * Every quoted item, from the first quote to delivery: client, product,
 * prices and discount, result, order, purchase order and supplier, goods in,
 * delivered, and how long it all took.
 */
export default function DealTrackerPage() {
  const params = useListParams();
  const period = (PERIODS.find((p) => p.value === params.get("period"))?.value ?? "all") as Period;
  const range = period === "custom" ? { from: params.get("from"), to: params.get("to") } : periodRange(period);
  const q = params.get("q");
  const stage = STAGES.find((s) => s.stage === params.get("stage"))?.stage;
  const filters = { q: q || undefined, from: range.from || undefined, to: range.to || undefined };

  // All stages are fetched once; the stage filter works on screen so the counts stay whole.
  const data = useQuery({
    meta: { silent: true },
    queryKey: ["deal-tracker", filters],
    queryFn: ({ signal }) => api.get<DealRow[]>("/deal-tracker", filters, signal),
  });
  const all = data.data ?? [];
  const rows = stage ? all.filter((r) => r.stage === stage) : all;

  function download(format: "xlsx" | "pdf") {
    const qs = new URLSearchParams({ format });
    if (q) qs.set("q", q);
    if (stage) qs.set("stage", stage);
    if (range.from) qs.set("from", range.from);
    if (range.to) qs.set("to", range.to);
    window.location.href = `/api/deal-tracker/export?${qs.toString()}`;
  }

  return (
    <>
      <PageHeader
        title="Deal Tracker"
        description="Each item from the first quote to delivery: client, prices, discount, order, supplier, goods in and delivered."
        actions={
          <div className="flex gap-2">
            <Button onClick={() => download("xlsx")}>Download Excel</Button>
            <Button variant="primary" onClick={() => download("pdf")}>
              Download PDF
            </Button>
          </div>
        }
      />
      <PageBody>
        <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-7">
          {STAGES.map((s) => {
            const count = all.filter((r) => r.stage === s.stage).length;
            const active = stage === s.stage;
            return (
              <button
                key={s.stage}
                type="button"
                onClick={() => params.set({ stage: active ? "" : s.stage })}
                className={`relative overflow-hidden p-3 text-left transition-colors hover:bg-hoverfill ${cardCls} ${active ? "ring-2 ring-brand" : ""}`}
              >
                <div aria-hidden className="pointer-events-none absolute -right-8 -top-10 size-32 rounded-full opacity-[0.16] blur-2xl" style={{ background: s.color }} />
                <p className={eyebrowCls}>{s.stage}</p>
                <p className="mt-1 text-xl font-semibold tabular-nums text-ink">{count}</p>
              </button>
            );
          })}
        </div>

        <FilterBar label="Deal tracker filters">
          <SearchInput
            label="Search deals"
            placeholder="Client, product, quote no. or supplier"
            value={q}
            onCommit={(v) => params.set({ q: v })}
          />
          <Select
            aria-label="Period"
            value={period}
            onChange={(e) => params.set({ period: e.target.value === "all" ? "" : e.target.value, from: "", to: "" })}
          >
            {PERIODS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </Select>
          {period === "custom" ? (
            <div className="flex items-center gap-2">
              <Input
                type="date"
                aria-label="From date"
                value={params.get("from")}
                onChange={(e) => params.set({ period: "custom", from: e.target.value, to: params.get("to") })}
              />
              <span className="text-[13px] text-ink-2">to</span>
              <Input
                type="date"
                aria-label="To date"
                value={params.get("to")}
                onChange={(e) => params.set({ period: "custom", from: params.get("from"), to: e.target.value })}
              />
            </div>
          ) : null}
          <div className="sm:col-span-2 lg:col-span-4">
            <FilterExtras>
              <p className="text-[13px] text-ink-2">
                {rows.length} {rows.length === 1 ? "item" : "items"} · prices before GST · the period is the first quote date
              </p>
              {params.hasFilters(KEYS) ? (
                <Button size="sm" onClick={() => params.clear(KEYS)}>
                  Clear filters
                </Button>
              ) : null}
            </FilterExtras>
          </div>
        </FilterBar>

        {data.isPending ? (
          <Loading />
        ) : data.isError ? (
          <ErrorState title="Could not load the deal tracker" error={data.error} onRetry={() => data.refetch()} />
        ) : rows.length === 0 ? (
          <EmptyState icon="inbox" title="Nothing here" description="No items match these filters." />
        ) : (
          <div className={`overflow-x-auto ${cardCls}`}>
            <table className="w-full min-w-[2600px] text-[12.5px]">
              <thead className="text-left text-[11px] font-medium uppercase tracking-wide text-ink-2">
                <tr className="border-b border-line">
                  <Th group="Quote" span={7} />
                  <Th group="Price" span={5} />
                  <Th group="Result" span={2} />
                  <Th group="Order" span={4} />
                  <Th group="Supplier" span={5} />
                  <Th group="Delivery" span={4} />
                </tr>
                <tr className="border-b border-line">
                  {[
                    "Client",
                    "Quote no.",
                    "Latest revision",
                    "Negotiation",
                    "Quote date",
                    "Product",
                    "Qty",
                    "Quoted",
                    "Revised",
                    "Final",
                    "Discount",
                    "Value",
                    "Result",
                    "Reason",
                    "Accepted",
                    "Order no.",
                    "From stock",
                    "Bought in",
                    "PO no.",
                    "Supplier",
                    "PO date",
                    "PO sent",
                    "Goods in",
                    "Delivered",
                    "Days",
                    "Where it is now",
                    "History",
                  ].map((h) => (
                    <th key={h} className="whitespace-nowrap px-2.5 py-2">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((r, i) => (
                  <tr key={`${r.quotation_id}-${i}`} className="hover:bg-hoverfill">
                    <td className="px-2.5 py-2 font-medium text-ink">{r.customer}</td>
                    <td className="whitespace-nowrap px-2.5 py-2">
                      <Link to={`/quotations/${r.original_id}`} className="text-ink hover:underline">
                        {r.quote_no}
                      </Link>
                    </td>
                    <td className="whitespace-nowrap px-2.5 py-2">
                      {r.revision_ref ? (
                        <Link to={`/negotiations/${r.quotation_id}`} className="hover:underline">
                          {r.revision_ref}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="whitespace-nowrap px-2.5 py-2">
                      {r.negotiation_ref ? (
                        <Link to={`/quotations/${r.quotation_id}`} className="hover:underline">
                          {r.negotiation_ref}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="whitespace-nowrap px-2.5 py-2 text-ink-2">{d(r.quote_date)}</td>
                    <td className="px-2.5 py-2 text-ink">{r.description}</td>
                    <td className="px-2.5 py-2 text-right tabular-nums">{r.quantity}</td>
                    <td className="whitespace-nowrap px-2.5 py-2 text-right tabular-nums">{formatRupees(r.quoted_paise)}</td>
                    <td className="whitespace-nowrap px-2.5 py-2 text-right tabular-nums">
                      {r.revised_paise === null ? "—" : formatRupees(r.revised_paise)}
                    </td>
                    <td className="whitespace-nowrap px-2.5 py-2 text-right tabular-nums">{formatRupees(r.final_paise)}</td>
                    <td className={`whitespace-nowrap px-2.5 py-2 text-right tabular-nums ${r.discount_paise > 0 ? "text-green" : "text-ink-2"}`}>
                      {r.discount_paise ? formatRupees(r.discount_paise) : "—"}
                    </td>
                    <td className="whitespace-nowrap px-2.5 py-2 text-right font-medium tabular-nums">{formatRupees(r.value_paise)}</td>
                    <td className="px-2.5 py-2">{r.result}</td>
                    <td className="px-2.5 py-2 text-ink-2">{r.decline_reason || "—"}</td>
                    <td className="whitespace-nowrap px-2.5 py-2 text-ink-2">{d(r.accepted_on)}</td>
                    <td className="whitespace-nowrap px-2.5 py-2">
                      {r.order_id ? (
                        <Link to={`/orders/${r.order_id}`} className="hover:underline">
                          {r.order_no}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-2.5 py-2 text-right tabular-nums">{n(r.from_stock)}</td>
                    <td className="px-2.5 py-2 text-right tabular-nums">{n(r.bought_in)}</td>
                    <td className="whitespace-nowrap px-2.5 py-2">
                      {r.po_id ? (
                        <Link to={`/purchase-orders/${r.po_id}`} className="hover:underline">
                          {r.po_no}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-2.5 py-2">{r.supplier || "—"}</td>
                    <td className="whitespace-nowrap px-2.5 py-2 text-ink-2">{d(r.po_date)}</td>
                    <td className="whitespace-nowrap px-2.5 py-2 text-ink-2">{d(r.po_sent)}</td>
                    <td className="whitespace-nowrap px-2.5 py-2 text-ink-2">{d(r.goods_received)}</td>
                    <td className="whitespace-nowrap px-2.5 py-2 text-ink-2">{d(r.delivered_on)}</td>
                    <td className="px-2.5 py-2 text-right tabular-nums">{n(r.days_to_deliver)}</td>
                    <td className="whitespace-nowrap px-2.5 py-2">
                      <span className="inline-flex items-center gap-1.5">
                        <span className="size-2 rounded-full" style={{ background: COLOR[r.stage] }} />
                        {r.stage}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-2.5 py-2">
                      <Link to={`/negotiations/${r.quotation_id}`} className="text-ink-2 hover:underline" title="Open every version">
                        {r.history}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </PageBody>
    </>
  );
}

function Th({ group, span }: { group: string; span: number }) {
  return (
    <th colSpan={span} className="border-r border-line px-2.5 pt-2 text-[10.5px] font-semibold tracking-wider text-ink last:border-r-0">
      {group}
    </th>
  );
}
