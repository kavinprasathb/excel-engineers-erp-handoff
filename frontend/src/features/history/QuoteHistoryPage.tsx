import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { Select } from "../../components/ui/Select";
import { Button } from "../../components/ui/Button";
import { Loading } from "../../components/ui/Spinner";
import { ErrorState } from "../../components/ui/ErrorState";
import { EmptyState } from "../../components/ui/EmptyState";
import { SearchInput } from "../../components/common/SearchInput";
import { FilterBar, FilterExtras } from "../../components/common/FilterBar";
import { cardCls } from "../../components/ui/styles";
import { api } from "../../api/client";
import { useListParams } from "../../lib/useListParams";
import { StatusBadge } from "../quotations/status";
import { STATUS_LABEL, formatRupees } from "../quotations/format";
import type { QuotationStatus } from "../../api/types";
import { Input } from "../../components/ui/Input";
import { PERIODS, periodRange, shortDate } from "./period";
import type { Period } from "./period";

interface HistoryRow {
  quotation_id: number;
  number: string;
  customer: string;
  description: string;
  quantity: number | null;
  quoted_paise: number | null;
  negotiations_paise: (number | null)[];
  /** Every version after the original, in order: "R1", "N1", "R2N1"... and the item's rate there. */
  stages: { label: string; rate_paise: number | null }[];
  /** The latest revised quotation's rate, before any negotiation of it. */
  revised_paise: number | null;
  /** The latest version's rate: where the deal stands now. */
  current_paise: number | null;
  original_number: string;
  stage: number;
  stage_label: string;
  status: QuotationStatus;
  decline_reason: string;
  quote_date: string;
}

const FILTER_KEYS = ["q", "status", "period", "from", "to"] as const;
const STATUSES: readonly QuotationStatus[] = ["pending", "accepted", "declined"];
const STAGES = Array.from({ length: 10 }, (_, i) => i + 1);

/** A rate cell: blank when that stage does not exist; green when it came down. */
function Rate({ value, previous }: { value: number | null; previous: number | null }) {
  if (value === null) return <span className="text-ink-2/40">—</span>;
  const tone =
    previous === null || value === previous ? "text-ink" : value < previous ? "text-green" : "text-red";
  return <span className={`tabular-nums ${tone}`}>{formatRupees(value)}</span>;
}

/**
 * End-to-end history, one row per item: who it was quoted to, what it is,
 * the quoted rate, the rate at each later version — revised quotations (R)
 * and negotiations (N), labelled — the current rate, and how it ended. One
 * row per item of a quotation number, so no deal is counted twice.
 */
export default function QuoteHistoryPage() {
  const navigate = useNavigate();
  const params = useListParams();
  const status = STATUSES.find((s) => s === params.get("status"));
  const q = params.get("q");
  // A named period is stored as its name, so "This month" stays this month
  // when the link is opened next month; only Custom stores dates.
  const period = (PERIODS.find((p) => p.value === params.get("period"))?.value ?? "all") as Period;
  const range =
    period === "custom" ? { from: params.get("from"), to: params.get("to") } : periodRange(period);

  const history = useQuery({
    meta: { silent: true },
    queryKey: ["quotations", "history", q, status ?? "", range.from, range.to],
    queryFn: ({ signal }) =>
      api.get<HistoryRow[]>(
        "/quotations/history",
        { q: q || undefined, status, from: range.from || undefined, to: range.to || undefined },
        signal,
      ),
  });

  const rows = history.data ?? [];
  const quoteCount = new Set(rows.map((r) => r.quotation_id)).size;

  // Same search and filter as the table, so the file is what is on screen.
  // A plain navigation: the session cookie authenticates it.
  function download(format: "xlsx" | "pdf") {
    const qs = new URLSearchParams({ format });
    if (q) qs.set("q", q);
    if (status) qs.set("status", status);
    if (range.from) qs.set("from", range.from);
    if (range.to) qs.set("to", range.to);
    window.location.href = `/api/quotations/history/export?${qs.toString()}`;
  }
  const filtered = params.hasFilters(FILTER_KEYS);

  return (
    <>
      <PageHeader
        title="Quote History"
        description="Every item, end to end: quoted price, each revised quotation and negotiation, and the result."
        actions={
          <div className="flex gap-2">
            <Button onClick={() => download("xlsx")}>Download Excel</Button>
            <Button onClick={() => download("pdf")}>Download PDF</Button>
          </div>
        }
      />
      <PageBody>
        <FilterBar label="Quote history filters">
          <SearchInput
            label="Search quote history"
            placeholder="Company, item, or number"
            value={q}
            onCommit={(v) => params.set({ q: v })}
          />
          <Select
            aria-label="Result"
            value={params.get("status")}
            onChange={(e) => params.set({ status: e.target.value })}
          >
            <option value="">Any result</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABEL[s]}
              </option>
            ))}
          </Select>
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
                max={params.get("to") || undefined}
                onChange={(e) => params.set({ period: "custom", from: e.target.value, to: params.get("to") })}
              />
              <span className="text-[13px] text-ink-2">to</span>
              <Input
                type="date"
                aria-label="To date"
                value={params.get("to")}
                min={params.get("from") || undefined}
                onChange={(e) => params.set({ period: "custom", from: params.get("from"), to: e.target.value })}
              />
            </div>
          ) : null}
          <div className="sm:col-span-2 lg:col-span-4">
            <FilterExtras>
              {range.from || range.to ? (
                <p className="text-[13px] text-ink-2">
                  Quoted {range.from ? shortDate(range.from) : "from the start"} to{" "}
                  {range.to ? shortDate(range.to) : "today"} · {quoteCount} {quoteCount === 1 ? "quote" : "quotes"}
                </p>
              ) : null}
              {filtered ? (
                <Button size="sm" onClick={() => params.clear(FILTER_KEYS)}>
                  Clear filters
                </Button>
              ) : (
                <p className="text-[13px] text-ink-2">
                  V1, V2…: each version after the original, labelled R (revised) or N (negotiation). Green: price came down. Click a row to open its history.
                </p>
              )}
            </FilterExtras>
          </div>
        </FilterBar>

        {history.isPending ? (
          <Loading />
        ) : history.isError ? (
          <ErrorState
            title="Could not load the quote history"
            error={history.error}
            onRetry={() => history.refetch()}
          />
        ) : rows.length === 0 ? (
          <div className={cardCls}>
            <EmptyState
              title={filtered ? "Nothing matches this filter" : "No quotations yet"}
              description={
                filtered ? "Try a different search, or clear the filters." : "Quotes appear here once written."
              }
            />
          </div>
        ) : (
          <div className={`overflow-x-auto ${cardCls}`}>
            <table className="w-full min-w-[1500px] text-[13px]">
              <thead className="bg-hoverfill text-left text-[11px] font-medium uppercase tracking-wide text-ink-2">
                <tr>
                  <th className="sticky left-0 z-10 bg-hoverfill px-3 py-2">Company</th>
                  <th className="px-3 py-2">Description</th>
                  <th className="px-3 py-2 text-right">Qty</th>
                  <th className="px-3 py-2 text-right">Quoted price</th>
                  <th className="px-3 py-2 text-right">Revised price</th>
                  {STAGES.map((n) => (
                    <th key={n} className="px-3 py-2 text-right">
                      V{n}
                    </th>
                  ))}
                  <th className="px-3 py-2 text-right">Current price</th>
                  <th className="min-w-[11rem] px-3 py-2">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((r, i) => {
                  const firstOfQuote = i === 0 || rows[i - 1].quotation_id !== r.quotation_id;
                  return (
                    <tr
                      key={`${r.quotation_id}-${i}`}
                      onClick={() => navigate(`/negotiations/${r.quotation_id}`)}
                      className={`cursor-pointer hover:bg-hoverfill ${firstOfQuote && i > 0 ? "border-t-2 border-line" : ""}`}
                    >
                      <td className="sticky left-0 z-10 bg-card px-3 py-2 align-top">
                        {firstOfQuote ? (
                          <>
                            <p className="font-medium text-ink">{r.customer}</p>
                            <p className="text-[12px] text-ink-2">{r.original_number}</p>
                          </>
                        ) : null}
                      </td>
                      <td className="px-3 py-2 text-ink">{r.description}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-ink">{r.quantity ?? "—"}</td>
                      <td className="px-3 py-2 text-right font-medium">
                        <Rate value={r.quoted_paise} previous={null} />
                      </td>
                      <td className="px-3 py-2 text-right">
                        <Rate value={r.revised_paise} previous={r.quoted_paise} />
                      </td>
                      {STAGES.map((n) => {
                        const v = r.stages[n - 1];
                        const prev = n === 1 ? r.quoted_paise : (r.stages[n - 2]?.rate_paise ?? null);
                        return (
                          <td key={n} className="px-3 py-2 text-right">
                            {v ? (
                              <>
                                <span className="block text-[10.5px] font-medium text-ink-2">{v.label}</span>
                                <Rate value={v.rate_paise} previous={prev} />
                              </>
                            ) : (
                              <Rate value={null} previous={null} />
                            )}
                          </td>
                        );
                      })}
                      <td className="px-3 py-2 text-right font-medium">
                        <Rate value={r.current_paise} previous={r.quoted_paise} />
                      </td>
                      <td className="px-3 py-2 align-top">
                        {firstOfQuote ? (
                          <div className="space-y-0.5">
                            <StatusBadge status={r.status} />
                            <p className="whitespace-nowrap text-[12px] text-ink-2">
                              {r.status === "pending" ? "Now at " : "At "}
                              {r.stage_label.toLowerCase()}
                            </p>
                            {r.status === "declined" && r.decline_reason ? (
                              <p className="max-w-[16rem] text-[12px] text-ink-2">{r.decline_reason}</p>
                            ) : null}
                          </div>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </PageBody>
    </>
  );
}
