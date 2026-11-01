import { Card } from "../../../components/ui/Card";
import { Loading } from "../../../components/ui/Spinner";
import { ErrorState } from "../../../components/ui/ErrorState";
import { Icon } from "../../../components/ui/Icon";
import type { IconName } from "../../../components/ui/Icon";
import { formatMoney, formatNumber } from "../../../lib/format";
import { useInventorySummary } from "../api";

type Tint = "blue" | "green" | "amber" | "red" | "violet";

const TINT: Record<Tint, { card: string; badge: string }> = {
  blue: { card: "bg-brand/[0.07] border-brand/15", badge: "bg-brand/15 text-brand" },
  green: { card: "bg-green-bg/70 border-green/15", badge: "bg-green/15 text-green" },
  amber: { card: "bg-amber-bg/70 border-amber/15", badge: "bg-amber/15 text-amber" },
  red: { card: "bg-red-bg/70 border-red/15", badge: "bg-red/15 text-red" },
  violet: { card: "bg-purple/[0.07] border-purple/15", badge: "bg-purple/15 text-purple" },
};

interface TileProps {
  label: string;
  value: string;
  icon: IconName;
  tint: Tint;
  tone?: "ink" | "amber" | "red";
  /** Turns the tile into the button that applies its own filter. */
  onClick?: () => void;
  active?: boolean;
}

function Tile({ label, value, icon, tint, tone = "ink", onClick, active }: TileProps) {
  // A zero is good news for the warning figures, so it stays neutral;
  // colouring it amber or red would cry wolf on a healthy shelf.
  const isZero = value === "0";
  const valueCls = isZero || tone === "ink" ? "text-heading" : tone === "red" ? "text-red" : "text-amber";

  const body = (
    <div className="flex items-center gap-3.5">
      <span className={`grid size-11 shrink-0 place-items-center rounded-full ${TINT[tint].badge}`}>
        <Icon name={icon} size={20} />
      </span>
      <div className="min-w-0">
        <p className="text-[13px] font-medium text-ink-2">{label}</p>
        <p
          className={`mt-0.5 font-display font-extrabold tracking-tight tabular-nums ${value.length > 9 ? "text-[19px]" : "text-[26px] leading-tight"} ${valueCls}`}
        >
          {value}
        </p>
        {onClick ? (
          <span className="block text-[12px] font-medium text-brand">{active ? "Showing these" : "Show these"}</span>
        ) : null}
      </div>
    </div>
  );

  const shell = `relative overflow-hidden rounded-2xl border p-4 text-left ${TINT[tint].card}`;
  if (!onClick) return <div className={shell}>{body}</div>;
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      title="Show only products with no supplier"
      className={`${shell} outline-none transition-shadow hover:shadow-md focus-visible:ring-2 focus-visible:ring-brand ${active ? "ring-2 ring-brand" : ""}`}
    >
      {body}
    </button>
  );
}

/**
 * Five figures the owner checks before anything else. `missing_supplier_count`
 * is the one that is actionable rather than informational, so it is the tile
 * you can press: it applies `has_supplier=false` to the list below.
 */
export function InventorySummaryCards({
  missingSupplierActive,
  onShowMissingSupplier,
}: {
  missingSupplierActive: boolean;
  onShowMissingSupplier: () => void;
}) {
  const summary = useInventorySummary();

  if (summary.isPending) {
    return (
      <Card className="mb-4 p-4">
        <Loading />
      </Card>
    );
  }

  if (summary.isError) {
    return (
      <div className="mb-4">
        <ErrorState title="Could not load the stock summary" error={summary.error} onRetry={() => summary.refetch()} />
      </div>
    );
  }

  const s = summary.data;

  return (
    <div
      className={`mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 ${s.total_stock_value_paise === null ? "" : "xl:grid-cols-5"}`}
    >
      <Tile label="Total items" value={formatNumber(s.total_products)} icon="inventory" tint="blue" />
      <Tile label="Low stock" value={formatNumber(s.low_stock_count)} tone="amber" icon="alert" tint="amber" />
      <Tile label="Out of stock" value={formatNumber(s.out_of_stock_count)} tone="red" icon="inbox" tint="red" />
      <Tile
        label="Missing supplier"
        value={formatNumber(s.missing_supplier_count)}
        tone="amber"
        icon="suppliers"
        tint="violet"
        active={missingSupplierActive}
        onClick={onShowMissingSupplier}
      />
      {s.total_stock_value_paise === null ? null : (
        <Tile label="Stock value" value={formatMoney(s.total_stock_value_paise)} icon="chart" tint="green" />
      )}
    </div>
  );
}
