import { useState } from "react";
import { Select } from "../../../components/ui/Select";
import { Icon } from "../../../components/ui/Icon";
import { Spinner } from "../../../components/ui/Spinner";
import { errorMessage } from "../../../lib/errors";
import { useSupplierOptions } from "../../suppliers/api";
import { useSetSupplier } from "../api";
import type { InventoryRow } from "../../../api/types";

/**
 * The fix for a real production failure.
 *
 * Imported products arrive with no supplier. In the previous version they were
 * indistinguishable from tagged ones in the list, and the gap only surfaced at
 * order confirmation, which refused the order with no indication of which
 * product was at fault. So an untagged row now flags itself in amber and can
 * be fixed in place — no drawer, no navigation, no losing the filter that
 * found it.
 */
export function SupplierCell({ row }: { row: InventoryRow }) {
  const [editing, setEditing] = useState(false);
  // Fetched only once a cell is actually opened. React Query dedupes the one
  // shared key, so opening a second cell costs no extra request.
  const options = useSupplierOptions(editing);
  const setSupplier = useSetSupplier();

  if (!editing) {
    if (row.supplier) {
      return <span className="text-ink">{row.supplier.name}</span>;
    }
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        className="inline-flex items-center gap-1 rounded-full bg-amber-bg px-2 py-1 text-[11px] font-medium text-amber transition-colors hover:opacity-90"
      >
        <Icon name="alert" size={13} />
        Set supplier
      </button>
    );
  }

  return (
    <div className="min-w-[10rem]">
      <div className="flex items-center gap-1.5">
        <Select
          aria-label={`Supplier for ${row.name}`}
          autoFocus
          disabled={setSupplier.isPending || options.isPending}
          defaultValue=""
          onChange={(e) => {
            const value = e.target.value;
            if (value === "") return;
            setSupplier.mutate(
              { productId: row.product_id, supplierId: Number(value) },
              // The mutation writes the refreshed row into the cache, so the
              // cell re-renders from the server's answer, not from this state.
              { onSuccess: () => setEditing(false) },
            );
          }}
        >
          <option value="">Choose a supplier…</option>
          {(options.data ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </Select>
        {setSupplier.isPending ? <Spinner /> : null}
        <button
          type="button"
          onClick={() => setEditing(false)}
          aria-label="Cancel setting supplier"
          className="shrink-0 rounded-lg border border-transparent p-1.5 text-ink-2 transition-colors hover:bg-hoverfill hover:text-ink"
        >
          <Icon name="close" size={15} />
        </button>
      </div>

      {options.isError ? (
        <p role="alert" className="mt-1 text-[12px] text-red">
          Could not load suppliers. {errorMessage(options.error)}
        </p>
      ) : null}
      {setSupplier.isError ? (
        <p role="alert" className="mt-1 text-[12px] text-red">
          {errorMessage(setSupplier.error)}
        </p>
      ) : null}
    </div>
  );
}
