import { useState } from "react";
import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PageBody } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Icon } from "../../components/ui/Icon";
import type { IconName } from "../../components/ui/Icon";
import { Loading } from "../../components/ui/Spinner";
import { badgeToneCls, cardCls, gutterCls, pageHeadingCls, selectCls } from "../../components/ui/styles";
import { useQuotationDashboard } from "../quotations/api";
import { formatQuoteDate, formatRupees } from "../quotations/format";
import type { QuotationDashboard } from "../../api/types";
import { ORDER_STATUS_LABEL, useOrders, usePurchaseOrders } from "../orders/api";
import type { OrderStatus } from "../orders/api";
import { useAnalytics } from "../analytics/api";
import type { Analytics } from "../analytics/api";
import { useInventorySummary } from "../inventory/api";
import { useNotifications } from "../notifications/api";
import type { Severity } from "../notifications/api";
import { useIsOwner } from "../auth/api";

// No change for this many days means someone should pick up the phone.
const STALE_DAYS = 15;

// Chart marks: one blue family plus the stage colours. Everything else uses tokens.
const BLUE = "#2f7cf6";
const BLUE_SOFT = "#a9c9fb";
const LINE = "#8b7cf0";
const TRACK = "var(--chart-track)";

const STAGES = [
  { key: "awaiting", label: "Awaiting reply", color: BLUE },
  { key: "negotiating", label: "In negotiation", color: "#f6b23c" },
  { key: "accepted", label: "Accepted", color: "#3ebd8a" },
  { key: "declined", label: "Declined", color: "#ee7b7b" },
] as const;

type Period = "month" | "quarter" | "year" | "all";
const PERIODS: { value: Period; label: string }[] = [
  { value: "month", label: "This month" },
  { value: "quarter", label: "Last 3 months" },
  { value: "year", label: "This year" },
  { value: "all", label: "All time" },
];

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** The analytics range for a period; "all" sends no bounds. */
function periodRange(p: Period, today = new Date()): { from: string; to: string } {
  if (p === "all") return { from: "", to: "" };
  const start =
    p === "month"
      ? new Date(today.getFullYear(), today.getMonth(), 1)
      : p === "quarter"
        ? new Date(today.getFullYear(), today.getMonth() - 2, 1)
        : new Date(today.getFullYear(), 0, 1);
  return { from: iso(start), to: iso(today) };
}

function daysSince(value: string): number {
  return Math.floor((Date.now() - new Date(value).getTime()) / 86_400_000);
}

/** ₹12.3L / ₹1.2Cr / ₹45K: short enough for an axis or a tooltip. */
function shortRupees(paise: number): string {
  const r = paise / 100;
  if (r >= 1e7) return `₹${(r / 1e7).toFixed(1).replace(/\.0$/, "")}Cr`;
  if (r >= 1e5) return `₹${(r / 1e5).toFixed(1).replace(/\.0$/, "")}L`;
  if (r >= 1e3) return `₹${Math.round(r / 1e3)}K`;
  return `₹${Math.round(r)}`;
}

/** A round axis step: 1, 2 or 5 times a power of ten, covering peak in four steps. */
function niceStep(peak: number, fallback: number): number {
  if (!peak) return fallback;
  const raw = peak / 4;
  const p = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 5, 10].map((m) => m * p).find((s) => s >= raw) ?? raw;
}

type Tone = "brand" | "amber" | "green" | "red" | "purple";
const TINT: Record<Tone, string> = {
  brand: "bg-brand/10 text-brand",
  amber: "bg-amber-bg text-amber",
  green: "bg-green-bg text-green",
  red: "bg-red-bg text-red",
  purple: "bg-purple/10 text-purple",
};

/**
 * The dealer's first look of the day: headline figures, sales, the quote
 * pipeline, what to follow up, and the latest orders. Every widget loads and
 * fails on its own, so a staff account (no analytics) still gets a full page.
 */
export default function DashboardPage() {
  const navigate = useNavigate();
  const owner = useIsOwner();
  const [period, setPeriod] = useState<Period>("year");
  const range = periodRange(period);
  const report = useAnalytics(range, owner);
  const dash = useQuotationDashboard();
  const periodLabel = PERIODS.find((p) => p.value === period)?.label ?? "";

  return (
    <>
      <header className={`pt-5 pb-1 sm:pt-7 ${gutterCls}`}>
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-brand/10 text-brand">
              <Icon name="chart" size={20} />
            </span>
            <div className="min-w-0">
              <h1 className={pageHeadingCls}>Dealer Dashboard</h1>
              <p className="mt-0.5 text-[13.5px] text-ink-2">
                Track sales, quotations, negotiations and business performance in one place.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {owner ? (
              <label className="flex items-center gap-2 text-[12.5px] text-ink-2">
                <span className="sr-only sm:not-sr-only">Sales period</span>
                <select
                  aria-label="Sales period"
                  className={`${selectCls} w-auto`}
                  value={period}
                  onChange={(e) => setPeriod(e.target.value as Period)}
                >
                  {PERIODS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <Button variant="primary" onClick={() => navigate("/quotations/new")}>
              <Icon name="plus" size={15} />
              Create Quotation
            </Button>
          </div>
        </div>
      </header>
      <PageBody>
        <div className="space-y-4">
          <Kpis owner={owner} report={report} dash={dash} periodLabel={periodLabel} />
          <div className="grid gap-4 xl:grid-cols-12">
            <div className="xl:col-span-8">
              <SalesOverview owner={owner} report={report} range={range} periodLabel={periodLabel} />
            </div>
            <div className="xl:col-span-4">
              <StageDonut dash={dash} />
            </div>
          </div>
          <div className="grid gap-4 xl:grid-cols-12">
            <div className="xl:col-span-7">
              <Pipeline dash={dash} />
            </div>
            <div className="xl:col-span-5">
              <FollowUps />
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-12">
            <div className="lg:col-span-2 xl:col-span-5">
              <RecentOrders />
            </div>
            <div className="xl:col-span-4">
              <TopProducts owner={owner} report={report} periodLabel={periodLabel} />
            </div>
            <div className="xl:col-span-3">
              <QuickActions owner={owner} />
            </div>
          </div>
        </div>
      </PageBody>
    </>
  );
}

type Query<T> = { data?: T; isPending: boolean; isError: boolean };

function Card({
  title,
  subtitle,
  right,
  children,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className={`flex h-full flex-col p-4 ${cardCls}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="font-display text-[16px] font-extrabold text-heading">{title}</h2>
          {subtitle ? <p className="text-[12.5px] text-ink-2">{subtitle}</p> : null}
        </div>
        {right}
      </div>
      <div className="mt-3 flex flex-1 flex-col">{children}</div>
    </section>
  );
}

function Note({ children }: { children: ReactNode }) {
  return <p className="flex flex-1 items-center justify-center py-10 text-center text-[13px] text-ink-2">{children}</p>;
}

/** Loading / error / content for one widget. */
function State<T>({ q, error, children }: { q: Query<T>; error: string; children: (d: T) => ReactNode }) {
  if (q.isPending)
    return (
      <div className="flex flex-1 items-center justify-center py-8">
        <Loading />
      </div>
    );
  if (q.isError || !q.data) return <Note>{error}</Note>;
  return <>{children(q.data)}</>;
}

/* ----------------------------------------------------------------- KPIs */

function KpiCard({
  icon,
  tone,
  label,
  value,
  sub,
  to,
}: {
  icon: IconName;
  tone: Tone;
  label: string;
  value: string;
  sub: string;
  to: string;
}) {
  return (
    <Link to={to} className={`flex items-start gap-3 p-4 transition-shadow hover:shadow-md ${cardCls}`}>
      <span className={`grid size-10 shrink-0 place-items-center rounded-full ${TINT[tone]}`}>
        <Icon name={icon} size={18} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[12.5px] leading-snug text-ink-2">{label}</p>
        <p className="mt-0.5 truncate font-display text-[22px] font-extrabold leading-tight tracking-tight tabular-nums text-heading">
          {value}
        </p>
        <p className="mt-0.5 line-clamp-2 text-[11.5px] leading-snug text-ink-2">{sub}</p>
      </div>
      <Icon name="chevronRight" size={15} className="shrink-0 text-ink-2" />
    </Link>
  );
}

function Kpis({
  owner,
  report,
  dash,
  periodLabel,
}: {
  owner: boolean;
  report: Query<Analytics>;
  dash: Query<QuotationDashboard>;
  periodLabel: string;
}) {
  const waiting = useOrders({ status: "waiting_stock" });
  const ready = useOrders({ status: "ready" });
  const stock = useInventorySummary();
  const d = dash.data;
  const b = d?.buckets;
  const dash_ = (v: string | undefined, loading: boolean) => v ?? (loading ? "…" : "–");

  const noReply = d ? d.awaiting.filter((r) => daysSince(r.quote_date) >= STALE_DAYS).length : 0;
  const pendingOrders =
    waiting.data && ready.data ? String(waiting.data.total + ready.data.total) : undefined;
  const alerts = stock.data ? String(stock.data.low_stock_count + stock.data.out_of_stock_count) : undefined;

  const sales = owner
    ? {
        label: "Total sales",
        value: dash_(report.data ? formatRupees(report.data.sales.value_paise) : undefined, report.isPending),
        sub: report.data
          ? `${report.data.sales.orders} delivered · ${periodLabel.toLowerCase()}`
          : `Delivered orders · ${periodLabel.toLowerCase()}`,
        to: "/analytics",
      }
    : {
        label: "Accepted quotes",
        value: dash_(b ? formatRupees(b.accepted.total_paise) : undefined, dash.isPending),
        sub: b ? `${b.accepted.count} accepted · current` : "Current",
        to: "/quotations?status=accepted",
      };

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
      <KpiCard icon="chart" tone="brand" {...sales} />
      <KpiCard
        icon="quotations"
        tone="amber"
        label="Pending quotations"
        value={dash_(b ? String(b.awaiting.count) : undefined, dash.isPending)}
        sub={d ? `${noReply} need follow-up (${STALE_DAYS}+ days)` : "Awaiting reply"}
        to="/quotations?status=pending"
      />
      <KpiCard
        icon="refresh"
        tone="purple"
        label="Active negotiations"
        value={dash_(b ? String(b.negotiating.count) : undefined, dash.isPending)}
        sub={b ? `${formatRupees(b.negotiating.total_paise)} in play` : "In negotiation"}
        to="/negotiations?status=pending"
      />
      <KpiCard
        icon="orders"
        tone="green"
        label="Pending orders"
        value={dash_(pendingOrders, waiting.isPending || ready.isPending)}
        sub={
          waiting.data && ready.data
            ? `${waiting.data.total} waiting stock · ${ready.data.total} ready`
            : "Not yet delivered"
        }
        to="/orders"
      />
      <KpiCard
        icon="alert"
        tone="red"
        label="Stock alerts"
        value={dash_(alerts, stock.isPending)}
        sub={
          stock.data
            ? `${stock.data.low_stock_count} low · ${stock.data.out_of_stock_count} out of stock`
            : "Low or out of stock"
        }
        to="/inventory"
      />
    </div>
  );
}

/* ------------------------------------------------------- Sales overview */

/** Months covered by the range; for "all time", the months the report has. */
function monthsFor(range: { from: string; to: string }, byMonth: Analytics["sales"]["by_month"]) {
  const keys: string[] = [];
  if (range.from) {
    const [y, m] = range.from.split("-").map(Number);
    const end = new Date();
    for (let d = new Date(y, m - 1, 1); d <= end; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) {
      keys.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
    }
  } else {
    keys.push(...byMonth.map((x) => x.month).sort());
  }
  return keys.map((key) => {
    const hit = byMonth.find((x) => x.month === key);
    const [y, m] = key.split("-").map(Number);
    const date = new Date(y, m - 1, 1);
    return {
      key,
      label: date.toLocaleString("en-IN", { month: "short" }),
      long: date.toLocaleString("en-IN", { month: "long", year: "numeric" }),
      value: hit?.value_paise ?? 0,
      orders: hit?.orders ?? 0,
    };
  });
}

function SalesOverview({
  owner,
  report,
  range,
  periodLabel,
}: {
  owner: boolean;
  report: Query<Analytics>;
  range: { from: string; to: string };
  periodLabel: string;
}) {
  const legend = (
    <div className="flex items-center gap-3 text-[11.5px] text-ink-2">
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-[3px]" style={{ background: BLUE }} />
        Sales value
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-0.5 w-3 rounded" style={{ background: LINE }} />
        Orders
      </span>
    </div>
  );
  return (
    <Card
      title="Sales Overview"
      subtitle={`Delivered orders, with GST · ${periodLabel.toLowerCase()}`}
      right={owner ? legend : undefined}
    >
      {!owner ? (
        <Note>Sales figures are visible to the owner.</Note>
      ) : (
        <State q={report} error="Could not load sales.">
          {(data) => <ComboChart months={monthsFor(range, data.sales.by_month)} />}
        </State>
      )}
    </Card>
  );
}

function ComboChart({ months }: { months: ReturnType<typeof monthsFor> }) {
  const [hover, setHover] = useState<number | null>(null);
  if (months.length === 0 || months.every((m) => m.value === 0 && m.orders === 0)) {
    return <Note>No orders delivered in this period yet.</Note>;
  }
  const vStep = niceStep(Math.max(...months.map((m) => m.value)), 100_000_00);
  const oPeak = Math.max(...months.map((m) => m.orders));
  const oStep = Math.max(1, Math.ceil(oPeak / 4));
  const W = 720;
  const H = 240;
  const padL = 52;
  const padR = 36;
  const top = 10;
  const padB = 26;
  const plotH = H - padB - top;
  const slot = (W - padL - padR) / months.length;
  const barW = Math.min(36, slot * 0.55);
  const yV = (v: number) => top + plotH - (v / (vStep * 4)) * plotH;
  const yO = (o: number) => top + plotH - (o / (oStep * 4)) * plotH;
  const cx = (i: number) => padL + slot * i + slot / 2;
  const path = months.map((m, i) => `${i ? "L" : "M"}${cx(i)},${yO(m.orders)}`).join(" ");
  const h = hover === null ? null : months[hover];

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Sales value and orders by month">
        {[0, 1, 2, 3, 4].map((i) => {
          const y = top + plotH - (i / 4) * plotH;
          return (
            <g key={i}>
              <line x1={padL} x2={W - padR} y1={y} y2={y} stroke={TRACK} strokeDasharray={i ? "4 4" : undefined} />
              <text x={padL - 8} y={y + 4} textAnchor="end" fontSize="11" fill="var(--text-secondary)">
                {shortRupees(vStep * i)}
              </text>
              <text x={W - padR + 8} y={y + 4} textAnchor="start" fontSize="11" fill="var(--text-secondary)">
                {oStep * i}
              </text>
            </g>
          );
        })}
        {months.map((m, i) => {
          const y = yV(m.value);
          return (
            <g key={m.key} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={padL + slot * i} y={top} width={slot} height={plotH} fill={hover === i ? TRACK : "transparent"} opacity={0.5} />
              {m.value > 0 ? (
                <rect
                  x={cx(i) - barW / 2}
                  y={y}
                  width={barW}
                  height={top + plotH - y}
                  rx={5}
                  fill={hover === i ? BLUE : BLUE_SOFT}
                />
              ) : null}
              {months.length <= 13 || i % 2 === 0 ? (
                <text x={cx(i)} y={H - 8} textAnchor="middle" fontSize="11" fill="var(--text-secondary)">
                  {m.label}
                </text>
              ) : null}
            </g>
          );
        })}
        <path d={path} fill="none" stroke={LINE} strokeWidth={2.5} strokeLinejoin="round" pointerEvents="none" />
        {months.map((m, i) => (
          <circle key={m.key} cx={cx(i)} cy={yO(m.orders)} r={hover === i ? 5 : 3.5} fill="var(--card)" stroke={LINE} strokeWidth={2} pointerEvents="none" />
        ))}
      </svg>
      {h && hover !== null ? (
        <div
          role="tooltip"
          className="pointer-events-none absolute top-1 -translate-x-1/2 rounded-lg border border-line bg-card px-3 py-2 text-[12px] shadow-md"
          style={{ left: `${(cx(hover) / W) * 100}%` }}
        >
          <p className="font-medium text-ink">{h.long}</p>
          <p className="tabular-nums text-ink-2">{formatRupees(h.value)}</p>
          <p className="tabular-nums text-ink-2">
            {h.orders} {h.orders === 1 ? "order" : "orders"}
          </p>
        </div>
      ) : null}
    </div>
  );
}

/* ----------------------------------------------------- Value by stage */

/** The analytics product list has no category, so the donut splits quote value by stage instead. */
function StageDonut({ dash }: { dash: Query<QuotationDashboard> }) {
  return (
    <Card title="Quote Value by Stage" subtitle="All quotations, before GST · current">
      <State q={dash} error="Could not load quotations.">
        {(d) => {
          const parts = STAGES.map((s) => ({ ...s, b: d.buckets[s.key] }));
          const sum = parts.reduce((n, p) => n + p.b.total_paise, 0);
          if (!sum) return <Note>No quotations yet.</Note>;
          const R = 54;
          const C = 2 * Math.PI * R;
          let offset = 0;
          return (
            <div className="flex flex-col items-center gap-4 sm:flex-row xl:flex-col 2xl:flex-row">
              <div className="relative size-40 shrink-0">
                <svg viewBox="0 0 140 140" className="size-full -rotate-90" role="img" aria-label="Quote value by stage">
                  <circle cx={70} cy={70} r={R} fill="none" stroke={TRACK} strokeWidth={18} />
                  {parts.map((p) => {
                    const len = (p.b.total_paise / sum) * C;
                    const el = (
                      <circle
                        key={p.key}
                        cx={70}
                        cy={70}
                        r={R}
                        fill="none"
                        stroke={p.color}
                        strokeWidth={18}
                        strokeDasharray={`${len} ${C - len}`}
                        strokeDashoffset={-offset}
                      />
                    );
                    offset += len;
                    return len > 0 ? el : null;
                  })}
                </svg>
                <div className="absolute inset-0 grid place-items-center text-center">
                  <div>
                    <p className="font-display text-[17px] font-extrabold tabular-nums text-heading">{shortRupees(sum)}</p>
                    <p className="text-[11px] text-ink-2">total</p>
                  </div>
                </div>
              </div>
              <ul className="w-full space-y-2 text-[12.5px]">
                {parts.map((p) => (
                  <li key={p.key} className="flex items-center gap-2">
                    <span className="size-2.5 shrink-0 rounded-[3px]" style={{ background: p.color }} />
                    <span className="min-w-0 flex-1 truncate text-ink-2">{p.label}</span>
                    <span className="font-medium tabular-nums text-ink">{shortRupees(p.b.total_paise)}</span>
                    <span className="w-10 text-right tabular-nums text-ink-2">
                      {Math.round((p.b.total_paise / sum) * 100)}%
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          );
        }}
      </State>
    </Card>
  );
}

/* ------------------------------------------------------------ Pipeline */

const STAGE_LINK: Record<(typeof STAGES)[number]["key"], string> = {
  awaiting: "/quotations?status=pending",
  negotiating: "/negotiations?status=pending",
  accepted: "/quotations?status=accepted",
  declined: "/quotations?status=declined",
};

function Pipeline({ dash }: { dash: Query<QuotationDashboard> }) {
  const sum = dash.data ? STAGES.reduce((n, s) => n + dash.data!.buckets[s.key].total_paise, 0) : 0;
  return (
    <Card
      title="Quotation & Negotiation Pipeline"
      subtitle="Current, all quotations"
      right={
        dash.data ? (
          <div className="text-right">
            <p className="text-[11.5px] text-ink-2">Total pipeline value</p>
            <p className="text-[16px] font-semibold tabular-nums text-ink">{formatRupees(sum)}</p>
          </div>
        ) : undefined
      }
    >
      <State q={dash} error="Could not load the pipeline.">
        {(d) => (
          <ol className="grid flex-1 grid-cols-1 items-stretch gap-2 sm:grid-cols-2 lg:flex">
            {STAGES.map((s, i) => {
              const b = d.buckets[s.key];
              const share = sum ? (b.total_paise / sum) * 100 : 0;
              return (
                <li key={s.key} className="flex min-w-0 flex-1 items-center gap-2">
                  <Link
                    to={STAGE_LINK[s.key]}
                    className="flex h-full min-w-0 flex-1 flex-col rounded-xl border border-line p-3 transition-colors hover:bg-hoverfill"
                  >
                    <span className="flex items-center gap-1.5 text-[12px] text-ink-2">
                      <span className="size-2 rounded-full" style={{ background: s.color }} />
                      <span className="truncate">{s.label}</span>
                    </span>
                    <span className="mt-1 font-display text-[22px] font-extrabold tabular-nums text-heading">{b.count}</span>
                    <span className="truncate text-[12px] tabular-nums text-ink-2">{formatRupees(b.total_paise)}</span>
                    <span className="mt-2 h-1 w-full overflow-hidden rounded-full bg-hoverfill">
                      <span className="block h-full rounded-full" style={{ width: `${share}%`, background: s.color }} />
                    </span>
                  </Link>
                  {i < STAGES.length - 1 ? (
                    <Icon name="chevronRight" size={16} className="hidden shrink-0 text-ink-2 lg:block" />
                  ) : null}
                </li>
              );
            })}
          </ol>
        )}
      </State>
    </Card>
  );
}

/* ---------------------------------------------------------- Follow-ups */

const SEVERITY_TONE: Record<Severity, string> = {
  critical: badgeToneCls.red,
  warning: badgeToneCls.amber,
  info: badgeToneCls.brand,
};
const SEVERITY_TEXT: Record<Severity, string> = { critical: "Urgent", warning: "Due", info: "Next step" };

function FollowUps() {
  const q = useNotifications();
  return (
    <Card
      title="Follow-ups Due"
      subtitle="Quotes, orders and purchase orders · current"
      right={
        <Link to="/notifications" className="text-[12.5px] font-medium text-brand hover:underline">
          View all
        </Link>
      }
    >
      <State q={q} error="Could not load follow-ups.">
        {(n) => {
          const items = n.items.filter((it) => it.category !== "inventory").slice(0, 6);
          if (!items.length) return <Note>Nothing to follow up. All clear.</Note>;
          return (
            <ul className="divide-y divide-line">
              {items.map((it) => (
                <li key={it.key} className="flex items-center gap-3 py-2.5">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium text-ink">{it.title}</p>
                    <p className="truncate text-[12px] text-ink-2">
                      {it.detail}
                      {it.days !== null ? ` · ${it.days} ${it.days === 1 ? "day" : "days"}` : ""}
                    </p>
                  </div>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${SEVERITY_TONE[it.severity]}`}>
                    {SEVERITY_TEXT[it.severity]}
                  </span>
                  <Link
                    to={it.link}
                    className="shrink-0 rounded-lg border border-line px-2.5 py-1 text-[12px] font-medium text-ink transition-colors hover:bg-hoverfill"
                  >
                    Open
                  </Link>
                </li>
              ))}
            </ul>
          );
        }}
      </State>
    </Card>
  );
}

/* -------------------------------------------------------- Recent orders */

const ORDER_TONE: Record<OrderStatus, string> = {
  waiting_stock: badgeToneCls.amber,
  ready: badgeToneCls.brand,
  delivered: badgeToneCls.green,
};

function RecentOrders() {
  const q = useOrders({});
  return (
    <Card
      title="Recent Orders"
      right={
        <Link to="/orders" className="text-[12.5px] font-medium text-brand hover:underline">
          View all
        </Link>
      }
    >
      <State q={q} error="Could not load orders.">
        {(page) => {
          const rows = page.items.slice(0, 5);
          if (!rows.length) return <Note>No orders yet. Accepted quotations become orders.</Note>;
          return (
            <div className="-mx-1 overflow-x-auto">
              <table className="w-full table-fixed text-[12.5px]">
                <thead>
                  <tr className="text-left">
                    <th className="w-[30%] rounded-l-lg px-2 py-2">Order</th>
                    <th className="px-2 py-2">Customer</th>
                    <th className="w-[20%] px-2 py-2 text-right">Value</th>
                    <th className="w-[18%] px-2 py-2">Status</th>
                    <th className="w-[17%] rounded-r-lg px-2 py-2 text-right">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((o) => (
                    <tr key={o.id} className="border-b border-line last:border-0">
                      <td className="px-2 py-2.5">
                        <Link to={`/orders/${o.id}`} className="block truncate font-medium tabular-nums text-ink hover:underline" title={o.number}>
                          {o.number}
                        </Link>
                      </td>
                      <td className="truncate px-2 py-2.5 text-ink-2" title={o.customer.name}>{o.customer.name}</td>
                      <td className="truncate px-2 py-2.5 text-right tabular-nums text-ink">{formatRupees(o.total_paise)}</td>
                      <td className="px-2 py-2.5">
                        <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium ${ORDER_TONE[o.status]}`}>
                          {o.status === "ready" ? "Ready" : ORDER_STATUS_LABEL[o.status]}
                        </span>
                      </td>
                      <td
                        className="whitespace-nowrap px-2 py-2.5 text-right tabular-nums text-ink-2"
                        title={formatQuoteDate(o.created_at.slice(0, 10))}
                      >
                        {formatQuoteDate(o.created_at.slice(0, 10)).slice(0, 5)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }}
      </State>
    </Card>
  );
}

/* ------------------------------------------------------- Top products */

function TopProducts({ owner, report, periodLabel }: { owner: boolean; report: Query<Analytics>; periodLabel: string }) {
  return (
    <Card title="Top Selling Products" subtitle={`By value won · ${periodLabel.toLowerCase()}`}>
      {!owner ? (
        <Note>Product sales are visible to the owner.</Note>
      ) : (
        <State q={report} error="Could not load products.">
          {(data) => {
            const rows = data.products
              .filter((p) => p.value_won_paise > 0)
              .sort((a, b) => b.value_won_paise - a.value_won_paise)
              .slice(0, 5);
            if (!rows.length) return <Note>No products won in this period yet.</Note>;
            const peak = rows[0].value_won_paise;
            return (
              <ol className="space-y-3">
                {rows.map((p, i) => (
                  <li key={p.description} className="flex items-center gap-3">
                    <span className="grid size-7 shrink-0 place-items-center rounded-full bg-hoverfill text-[12px] font-semibold text-ink-2">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <p className="truncate text-[13px] text-ink" title={p.description}>
                          {p.description}
                        </p>
                        <p className="shrink-0 text-[12.5px] font-medium tabular-nums text-ink">{shortRupees(p.value_won_paise)}</p>
                      </div>
                      <div className="mt-1 flex items-center gap-2">
                        <span className="h-1 flex-1 overflow-hidden rounded-full bg-hoverfill">
                          <span className="block h-full rounded-full" style={{ width: `${(p.value_won_paise / peak) * 100}%`, background: BLUE }} />
                        </span>
                        <span className="shrink-0 text-[11.5px] tabular-nums text-ink-2">{p.qty_won} units</span>
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            );
          }}
        </State>
      )}
    </Card>
  );
}

/* ------------------------------------------------------- Quick actions */

function QuickActions({ owner }: { owner: boolean }) {
  const unsent = usePurchaseOrders({ status: "draft" });
  const actions: { icon: IconName; tone: Tone; label: string; to: string }[] = [
    { icon: "quotations", tone: "brand", label: "New quotation", to: "/quotations/new" },
    { icon: "customers", tone: "green", label: "Customers", to: "/customers" },
    { icon: "products", tone: "purple", label: owner ? "Products & import" : "Products", to: "/products" },
    {
      icon: "purchaseOrders",
      tone: "amber",
      label: unsent.data?.total ? `${unsent.data.total} POs to send` : "Purchase orders",
      to: unsent.data?.total ? "/purchase-orders?status=draft" : "/purchase-orders",
    },
  ];
  return (
    <Card title="Quick Actions">
      <div className="grid flex-1 grid-cols-2 gap-3">
        {actions.map((a) => (
          <Link
            key={a.label}
            to={a.to}
            className="flex flex-col items-center justify-center gap-2 rounded-xl border border-line p-3 text-center transition-colors hover:bg-hoverfill"
          >
            <span className={`grid size-10 place-items-center rounded-full ${TINT[a.tone]}`}>
              <Icon name={a.icon} size={18} />
            </span>
            <span className="text-[12.5px] font-medium text-ink">{a.label}</span>
          </Link>
        ))}
      </div>
    </Card>
  );
}
