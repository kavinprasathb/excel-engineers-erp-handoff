import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { Select } from "../../components/ui/Select";
import { Input } from "../../components/ui/Input";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Art } from "../../components/illustrations/Art";
import { ICON_ART } from "../../components/illustrations/art-map";
import type { IconName } from "../../components/ui/Icon";
import { Loading } from "../../components/ui/Spinner";
import { ErrorState } from "../../components/ui/ErrorState";
import { cardCls, eyebrowCls } from "../../components/ui/styles";
import { useListParams } from "../../lib/useListParams";
import { formatQuoteDate, formatRupees } from "../quotations/format";
import { PERIODS, periodRange, shortDate } from "../history/period";
import type { Period } from "../history/period";
import { LOST, OPEN, OTHER_GREY, SERIES, WON, analyticsPdfUrl, useAnalytics } from "./api";
import type { Analytics } from "./api";
import { Columns, Donut } from "./charts";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function monthLabel(ym: string): string {
  const [y, m] = ym.split("-");
  return `${MONTHS[Number(m) - 1]} ${y}`;
}

function pct(v: number | null): string {
  return v === null ? "—" : `${v}%`;
}

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** Where the quotes go, what sells, and what to chase. */
export default function AnalyticsPage() {
  const params = useListParams();
  const period = (PERIODS.find((p) => p.value === params.get("period"))?.value ?? "this-year") as Period;
  const range = period === "custom" ? { from: params.get("from"), to: params.get("to") } : periodRange(period);
  const report = useAnalytics(range);

  return (
    <>
      <PageHeader
        title="Analytics"
        description="How quotes convert, what sells, and where deals get stuck. Amounts include 18% GST."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Select
              aria-label="Period"
              value={period}
              onChange={(e) => params.set({ period: e.target.value, from: "", to: "" })}
            >
              {PERIODS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </Select>
            {period === "custom" ? (
              <>
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
              </>
            ) : null}
            <Button variant="primary" onClick={() => window.open(analyticsPdfUrl(range), "_blank")}>
              Download PDF
            </Button>
          </div>
        }
      />
      <PageBody>
        {range.from || range.to ? (
          <p className="mb-3 text-[13px] text-ink-2">
            {range.from ? shortDate(range.from) : "From the start"} to {range.to ? shortDate(range.to) : "today"}.
            Quotes count by the day they were first sent; sales by the day of Product Delivery.
          </p>
        ) : null}
        {report.isPending ? (
          <Loading />
        ) : report.isError ? (
          <ErrorState title="Could not load analytics" error={report.error} onRetry={() => report.refetch()} />
        ) : (
          <Report a={report.data} />
        )}
      </PageBody>
    </>
  );
}

function Report({ a }: { a: Analytics }) {
  const c = a.conversion;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Tile
          icon="quotations"
          accent="#2a78d6"
          label="Quotes given"
          value={String(c.quoted)}
          sub={`worth ${formatRupees(c.quoted_value_paise)}`}
        />
        <Tile
          icon="check"
          accent="#1baf7a"
          label="Win rate"
          value={pct(c.rate_answered)}
          sub={`${c.accepted_count} won of ${c.accepted_count + c.declined_count} answered`}
        />
        <Tile
          icon="orders"
          accent="#4a3aa7"
          label="Sales (delivered)"
          value={formatRupees(a.sales.value_paise)}
          sub={`${plural(a.sales.orders, "order", "orders")} delivered`}
        />
        <Tile
          icon="alert"
          accent="#eda100"
          label="Money still to win"
          value={formatRupees(a.pipeline.value_paise)}
          sub={`${a.pipeline.count} open · ${a.pipeline.follow_up_count} need a call`}
        />
      </div>

      <Highlights a={a} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Conversion a={a} />
        <Reasons a={a} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Sales a={a} />
        <TopCustomers a={a} />
      </div>

      <Customers a={a} />
      <Products a={a} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Discount a={a} />
        <TimeToClose a={a} />
      </div>

      <Reorder a={a} />
      <Pipeline a={a} />
    </div>
  );
}

function Tile({
  icon,
  accent,
  label,
  value,
  sub,
}: {
  icon: IconName;
  accent: string;
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className={`relative overflow-hidden p-4 ${cardCls}`}>
      <div aria-hidden className="pointer-events-none absolute -right-8 -top-10 size-32 rounded-full opacity-[0.16] blur-2xl" style={{ background: accent }} />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className={eyebrowCls}>{label}</p>
          <p className="mt-1.5 text-2xl font-semibold tracking-tight tabular-nums text-ink">{value}</p>
          <p className="mt-0.5 text-[12px] tabular-nums text-ink-2">{sub}</p>
        </div>
        <Art name={ICON_ART[icon] ?? "chart"} size={52} className="-my-2 -mr-2 shrink-0" />
      </div>
    </div>
  );
}

/** Plain sentences the owner can act on today. */
function Highlights({ a }: { a: Analytics }) {
  const topReason = a.conversion.reasons[0];
  const topCustomer = [...a.customers].sort((x, y) => y.sales_paise - x.sales_paise || y.quotes - x.quotes)[0];
  const neverWon = a.products
    .filter((p) => p.times_won === 0)
    .sort((x, y) => y.value_quoted_paise - x.value_quoted_paise)[0];
  const items: { key: string; tone: string; text: ReactNode }[] = [];
  if (topCustomer)
    items.push({
      key: "customer",
      tone: "#1baf7a",
      text: (
        <>
          Best customer: <b>{topCustomer.customer}</b> — {plural(topCustomer.quotes, "quote", "quotes")},{" "}
          {topCustomer.accepted} won.
        </>
      ),
    });
  if (topReason)
    items.push({
      key: "reason",
      tone: "#e34948",
      text: (
        <>
          Top reason for losing: <b>{topReason.reason}</b> ({topReason.count} of {a.conversion.declined_count}).
        </>
      ),
    });
  if (a.pipeline.follow_up_count > 0)
    items.push({
      key: "follow",
      tone: "#eda100",
      text: (
        <>
          <b>{a.pipeline.follow_up_count}</b> pending{" "}
          {a.pipeline.follow_up_count === 1 ? "quote needs" : "quotes need"} a follow-up call.
        </>
      ),
    });
  else if (neverWon)
    items.push({
      key: "lost",
      tone: "#eda100",
      text: (
        <>
          Quoted but never won: <b>{neverWon.description}</b> ({formatRupees(neverWon.value_quoted_paise)} quoted).
        </>
      ),
    });
  if (items.length === 0) return null;
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {items.map((it) => (
        <div key={it.key} className={`flex items-start gap-2.5 p-3 text-[13px] text-ink ${cardCls}`}>
          <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: it.tone }} />
          <p>{it.text}</p>
        </div>
      ))}
    </div>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="text-[13px] text-ink-2">{children}</p>;
}

function Conversion({ a }: { a: Analytics }) {
  const c = a.conversion;
  return (
    <Card>
      <CardHeader
        title="Quote conversion"
        description={`${pct(c.rate_all)} of all quotes won; ${pct(c.rate_answered)} of those the customer answered.`}
      />
      <CardBody>
        {c.quoted === 0 ? (
          <Empty>No quotes in this period.</Empty>
        ) : (
          <Donut
            center={pct(c.rate_answered)}
            sub="win rate"
            slices={[
              {
                label: "Accepted",
                value: c.accepted_count,
                color: WON,
                detail: formatRupees(c.accepted_value_paise),
              },
              {
                label: "Declined",
                value: c.declined_count,
                color: LOST,
                detail: formatRupees(c.declined_value_paise),
              },
              {
                label: "Still pending",
                value: c.pending_count,
                color: OPEN,
                detail: formatRupees(c.pending_value_paise),
              },
            ]}
          />
        )}
      </CardBody>
    </Card>
  );
}

function Reasons({ a }: { a: Analytics }) {
  const c = a.conversion;
  let slot = 0;
  const slices = c.reasons.map((r) => ({
    label: r.reason,
    value: r.count,
    color: r.reason === "Other" ? OTHER_GREY : SERIES[slot++ % SERIES.length],
  }));
  return (
    <Card>
      <CardHeader title="Why quotes were declined" description="Fix the biggest slice first." />
      <CardBody>
        {c.reasons.length === 0 ? (
          <Empty>Nothing declined in this period.</Empty>
        ) : (
          <>
            <Donut slices={slices} center={c.declined_count} sub="declined" />
            <details className="mt-3 text-[13px]">
              <summary className="cursor-pointer text-ink-2">Each declined quote</summary>
              <ul className="mt-2 divide-y divide-line">
                {c.declined.map((d) => (
                  <li key={d.id} className="py-1.5">
                    <Link to={`/quotations/${d.id}`} className="font-medium text-ink hover:underline">
                      {d.number}
                    </Link>{" "}
                    <span className="text-ink-2">
                      {d.customer} · {formatRupees(d.value_paise)} · {d.reason || "no reason recorded"}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          </>
        )}
      </CardBody>
    </Card>
  );
}

function Sales({ a }: { a: Analytics }) {
  const s = a.sales;
  return (
    <Card>
      <CardHeader title="Sales by month" description={`Delivered orders. Average order ${formatRupees(s.average_paise)}.`} />
      <CardBody>
        {s.by_month.length === 0 ? (
          <Empty>No deliveries in this period.</Empty>
        ) : (
          <Columns
            format={formatRupees}
            data={s.by_month.map((m) => ({
              label: monthLabel(m.month),
              value: m.value_paise,
              note: plural(m.orders, "order", "orders"),
            }))}
          />
        )}
      </CardBody>
    </Card>
  );
}

/** Who brings the business: share of quotes by customer, top 5 and the rest. */
function TopCustomers({ a }: { a: Analytics }) {
  const sorted = [...a.customers].sort((x, y) => y.quotes - x.quotes);
  const rest = sorted.slice(5).reduce((n, c) => n + c.quotes, 0);
  const slices = sorted
    .slice(0, 5)
    .map((c, i) => ({ label: c.customer, value: c.quotes, color: SERIES[i], detail: `${c.accepted} won` }));
  if (rest > 0) slices.push({ label: "All others", value: rest, color: OTHER_GREY, detail: "" });
  const repeat = a.customers.filter((c) => c.repeat).length;
  return (
    <Card>
      <CardHeader
        title="Who asks for quotes"
        description={`${repeat} of ${plural(a.customers.length, "customer", "customers")} came back for more than one quote.`}
      />
      <CardBody>
        {slices.length === 0 ? (
          <Empty>No customers in this period.</Empty>
        ) : (
          <Donut
            slices={slices}
            center={a.customers.length}
            sub={a.customers.length === 1 ? "customer" : "customers"}
          />
        )}
      </CardBody>
    </Card>
  );
}

function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-[13px]">
        <thead className="text-left text-[11px] font-medium uppercase tracking-wide text-ink-2">
          <tr className="border-b border-line">
            {head.map((h, i) => (
              <th key={h} className={`px-2 py-2 ${i === 0 ? "" : "text-right"}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  );
}

const num = "px-2 py-2 text-right tabular-nums text-ink";

function Customers({ a }: { a: Analytics }) {
  return (
    <Card>
      <CardHeader title="Customers" description="Most quotes first. Repeat customers are marked." />
      <CardBody>
        {a.customers.length === 0 ? (
          <Empty>No customers in this period.</Empty>
        ) : (
          <Table head={["Customer", "Quotes", "Won", "Declined", "Win rate", "Quoted", "Sales", "Last quote"]}>
            {a.customers.map((c) => (
              <tr key={c.customer_id}>
                <td className="px-2 py-2 text-ink">
                  {c.customer} {c.repeat ? <Badge tone="brand">Repeat</Badge> : null}
                </td>
                <td className={num}>{c.quotes}</td>
                <td className={num}>{c.accepted}</td>
                <td className={num}>{c.declined}</td>
                <td className={num}>{pct(c.rate)}</td>
                <td className={num}>{formatRupees(c.quoted_value_paise)}</td>
                <td className={num}>{formatRupees(c.sales_paise)}</td>
                <td className={num}>{c.last_quote ? formatQuoteDate(c.last_quote) : "—"}</td>
              </tr>
            ))}
          </Table>
        )}
      </CardBody>
    </Card>
  );
}

function Products({ a }: { a: Analytics }) {
  return (
    <Card>
      <CardHeader
        title="Products"
        description="Quoted against won. A product quoted often but rarely won needs a price or supply check."
      />
      <CardBody>
        {a.products.length === 0 ? (
          <Empty>No products quoted in this period.</Empty>
        ) : (
          <Table
            head={["Product", "Times quoted", "Qty quoted", "Quoted value", "Times won", "Qty won", "Won value", "Win rate"]}
          >
            {a.products.map((p) => (
              <tr key={p.description}>
                <td className="px-2 py-2 text-ink">{p.description}</td>
                <td className={num}>{p.times_quoted}</td>
                <td className={num}>{p.qty_quoted}</td>
                <td className={num}>{formatRupees(p.value_quoted_paise)}</td>
                <td className={num}>{p.times_won}</td>
                <td className={num}>{p.qty_won}</td>
                <td className={num}>{formatRupees(p.value_won_paise)}</td>
                <td className={`${num} ${p.times_quoted >= 3 && (p.rate ?? 0) < 25 ? "text-red" : ""}`}>
                  {pct(p.rate)}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </CardBody>
    </Card>
  );
}

function Discount({ a }: { a: Analytics }) {
  const d = a.discount;
  return (
    <Card>
      <CardHeader
        title="Discount given in negotiation"
        description={
          d.won_quotes === 0
            ? "No quotes won in this period."
            : `${formatRupees(d.discount_paise)} (${pct(d.discount_pct)}) off the first price, across ${plural(d.won_quotes, "won quote", "won quotes")}; ${d.negotiated} negotiated.`
        }
      />
      <CardBody>
        {d.rows.length === 0 ? (
          <Empty>No won quote was negotiated down.</Empty>
        ) : (
          <ul className="divide-y divide-line text-[13px]">
            {d.rows.map((r) => (
              <li key={r.id} className="flex flex-wrap items-baseline justify-between gap-2 py-1.5">
                <span>
                  <Link to={`/quotations/${r.id}`} className="font-medium text-ink hover:underline">
                    {r.number}
                  </Link>{" "}
                  <span className="text-ink-2">
                    {r.customer} · {r.stage_label} · {plural(r.rounds, "round", "rounds")}
                  </span>
                </span>
                <span className="tabular-nums text-ink">
                  {formatRupees(r.first_paise)} →{" "}
                  {r.revised_paise !== null ? (
                    <>
                      <span title="Revised quotation, before negotiation">{formatRupees(r.revised_paise)}</span> →{" "}
                    </>
                  ) : null}
                  {formatRupees(r.final_paise)}{" "}
                  <span className="text-green">−{pct(r.discount_pct)}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

function TimeToClose({ a }: { a: Analytics }) {
  const t = a.time_to_close;
  const days = (v: number | null) => (v === null ? "—" : `${v} days`);
  return (
    <Card>
      <CardHeader title="Time to close" description="From the first quote to the customer's answer." />
      <CardBody>
        <dl className="grid grid-cols-3 gap-3 text-[13px]">
          <div className="rounded-lg bg-green-bg p-3">
            <dt className="text-ink-2">To win</dt>
            <dd className="text-lg font-semibold tabular-nums text-ink">{days(t.accepted_avg_days)}</dd>
          </div>
          <div className="rounded-lg bg-red-bg p-3">
            <dt className="text-ink-2">To lose</dt>
            <dd className="text-lg font-semibold tabular-nums text-ink">{days(t.declined_avg_days)}</dd>
          </div>
          <div className="rounded-lg bg-hoverfill p-3">
            <dt className="text-ink-2">Negotiations to win</dt>
            <dd className="text-lg font-semibold tabular-nums text-ink">{t.avg_rounds_to_win ?? "—"}</dd>
          </div>
        </dl>
      </CardBody>
    </Card>
  );
}

/** What to buy now, from how fast each product sells. */
function Reorder({ a }: { a: Analytics }) {
  const r = a.reorder;
  return (
    <Card>
      <CardHeader
        title="Reorder suggestions"
        description={
          r.count === 0
            ? "Nothing to buy right now. Stock and open purchase orders cover what is selling."
            : `${plural(r.count, "product", "products")} to buy, about ${formatRupees(r.value_paise)} at cost. Based on the last ${r.window_days} days of deliveries, a ${r.lead_days}-day supplier wait and ${r.cover_days} days of stock after it arrives.`
        }
      />
      <CardBody>
        {r.rows.length === 0 ? (
          <Empty>All stocked.</Empty>
        ) : (
          <Table head={["Product", "Free stock", "On order", "Sells / month", "Lasts", "Buy", "Cost", "Why"]}>
            {r.rows.map((p) => (
              <tr key={p.product_id}>
                <td className="px-2 py-2 text-ink">
                  <p>
                    {p.name} {p.urgent ? <Badge tone="red">Urgent</Badge> : null}
                  </p>
                  <p className="text-[12px] text-ink-2">
                    {p.sku}
                    {p.supplier ? ` · ${p.supplier}` : " · no supplier"}
                  </p>
                </td>
                <td className={num}>{p.available}</td>
                <td className={num}>{p.on_order}</td>
                <td className={num}>{p.per_month}</td>
                <td className={num}>{p.days_left === null ? "—" : `${p.days_left} days`}</td>
                <td className={`${num} font-semibold`}>{p.suggest}</td>
                <td className={num}>{formatRupees(p.value_paise)}</td>
                <td className="px-2 py-2 text-right text-[12px] text-ink-2">{p.reason}</td>
              </tr>
            ))}
          </Table>
        )}
      </CardBody>
    </Card>
  );
}

function Pipeline({ a }: { a: Analytics }) {
  const p = a.pipeline;
  return (
    <Card>
      <CardHeader
        title="Pending quotes to follow up"
        description={`All open quotes, oldest first. ${p.follow_up_count} have had no change in ${p.follow_up_days} days or more — call these customers.`}
      />
      <CardBody>
        {p.rows.length === 0 ? (
          <Empty>No pending quotes.</Empty>
        ) : (
          <Table head={["Quote", "Customer", "First sent", "Last change", "Age", "Value"]}>
            {p.rows.map((r) => (
              <tr key={r.id}>
                <td className="px-2 py-2">
                  <Link to={`/quotations/${r.id}`} className="font-medium text-ink hover:underline">
                    {r.number}
                  </Link>{" "}
                  {r.follow_up ? <Badge tone="amber">Follow up</Badge> : null}
                </td>
                <td className="px-2 py-2 text-right text-ink">{r.customer}</td>
                <td className={num}>{formatQuoteDate(r.quote_date)}</td>
                <td className={num}>{formatQuoteDate(r.last_change)}</td>
                <td className={num}>{r.age_days} days</td>
                <td className={num}>{formatRupees(r.value_paise)}</td>
              </tr>
            ))}
          </Table>
        )}
      </CardBody>
    </Card>
  );
}
