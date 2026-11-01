import { Button } from "../../../components/ui/Button";
import { Icon } from "../../../components/ui/Icon";
import { cardCls } from "../../../components/ui/styles";
import { formatNumber, orDash } from "../../../lib/format";
import { ProductThumb, StockStatusPill } from "./ProductThumb";
import type { InventoryRow } from "../../../api/types";

const TIPS = [
  "Keep track of low stock items and reorder before they run out.",
  "Update stock after every transaction.",
  "Ensure the quantity on the shelf matches the quantity here.",
];

function Header() {
  return (
    <svg viewBox="0 0 280 96" className="h-full w-full" aria-hidden="true" preserveAspectRatio="xMidYMid slice">
      <defs>
        <linearGradient id="qv-bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#0b2d6b" />
          <stop offset="1" stopColor="#1d5fc4" />
        </linearGradient>
      </defs>
      <rect width="280" height="96" fill="url(#qv-bg)" />
      <g fill="#ffffff" fillOpacity="0.08">
        <circle cx="240" cy="10" r="60" />
        <circle cx="30" cy="100" r="44" />
      </g>
      <g stroke="#ffffff" strokeOpacity="0.18" fill="none">
        <path d="M0 76h280M0 60h280" strokeDasharray="2 6" />
      </g>
    </svg>
  );
}

/** The selected row at a glance, beside the table on wide screens. */
export function InventoryQuickView({ row, onHistory }: { row: InventoryRow | null; onHistory: (row: InventoryRow) => void }) {
  return (
    <aside aria-label="Quick view" className="sticky top-4 space-y-4">
      <div className={`overflow-hidden ${cardCls}`}>
        <div className="flex items-center justify-between px-4 py-3">
          <h2 className="font-display text-[15px] font-bold text-heading">Quick View</h2>
        </div>
        {row ? (
          <>
            <div className="relative h-24">
              <Header />
              <div className="absolute inset-0 grid place-items-center">
                <span className="rounded-xl bg-card p-1.5 shadow-lg">
                  <ProductThumb row={row} size={52} />
                </span>
              </div>
            </div>
            <div className="p-4">
              <p className="font-display text-[15px] font-bold leading-snug text-heading">{row.name}</p>
              <p className="mt-0.5 text-[12px] text-ink-2">{row.sku}</p>
              <dl className="mt-3 space-y-1.5 text-[13px]">
                {[
                  ["Model", orDash(row.model_number || null)],
                  ["Supplier", orDash(row.supplier?.name)],
                  ["Category", orDash(row.category?.name)],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3">
                    <dt className="text-ink-2">{k}</dt>
                    <dd className="truncate text-right font-medium text-ink">{v}</dd>
                  </div>
                ))}
              </dl>
              <div className="mt-3 grid grid-cols-3 gap-2 rounded-xl bg-app-bg p-2 text-center">
                {[
                  ["On hand", row.quantity_on_hand],
                  ["Reserved", row.quantity_reserved],
                  ["Available", row.quantity_available],
                ].map(([k, v]) => (
                  <div key={k}>
                    <p className="text-[11px] text-ink-2">{k}</p>
                    <p className="font-display text-[16px] font-bold tabular-nums text-heading">{formatNumber(Number(v))}</p>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex items-center justify-between">
                <span className="text-[12px] text-ink-2">Status</span>
                <StockStatusPill row={row} />
              </div>
              <Button fullWidth className="mt-4" onClick={() => onHistory(row)}>
                <Icon name="refresh" size={15} />
                View History
              </Button>
            </div>
          </>
        ) : (
          <p className="px-4 pb-4 text-[13px] text-ink-2">Select a row to see it here.</p>
        )}
      </div>

      <div className="rounded-2xl border border-brand/15 bg-brand/[0.06] p-4">
        <p className="flex items-center gap-2 font-display text-[14px] font-bold text-heading">
          <Icon name="info" size={16} className="text-brand" />
          Inventory Tips
        </p>
        <ul className="mt-2 space-y-1.5 text-[12.5px] text-ink-2">
          {TIPS.map((t) => (
            <li key={t} className="flex gap-2">
              <Icon name="check" size={14} className="mt-0.5 text-brand" />
              {t}
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
