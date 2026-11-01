import { Chip } from "../../../components/ui/Chip";
import { formatNumber } from "../../../lib/format";
import type { InventoryRow } from "../../../api/types";

/**
 * The server owns both the arithmetic and the rule.
 *
 * `quantity_available` is rendered exactly as sent — never `on_hand - reserved`
 * — and the colour comes from `is_out_of_stock` / `is_low_stock`, which are
 * computed against the settings threshold server-side. If this component ever
 * compares a number to a threshold, the app and the server can disagree about
 * what is low, and the person reading the screen has no way to tell which is
 * right.
 */
export function AvailabilityCell({ row }: { row: InventoryRow }) {
  const numberCls = row.is_out_of_stock
    ? "text-red"
    : row.is_low_stock
      ? "text-amber"
      : "text-ink";

  return (
    <span className="inline-flex items-center justify-end gap-2">
      <span className={`font-medium tabular-nums ${numberCls}`}>
        {formatNumber(row.quantity_available)}
      </span>
      {/* Colour is never the only signal, so the state is also a word. */}
      {row.is_out_of_stock ? (
        <Chip tone="red">Out of stock</Chip>
      ) : row.is_low_stock ? (
        <Chip tone="amber">Low</Chip>
      ) : null}
    </span>
  );
}
