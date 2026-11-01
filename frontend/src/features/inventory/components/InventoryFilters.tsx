import { Select } from "../../../components/ui/Select";
import { SegmentedControl } from "../../../components/ui/SegmentedControl";
import { Button } from "../../../components/ui/Button";
import { Icon } from "../../../components/ui/Icon";
import { SearchInput } from "../../../components/common/SearchInput";
import { FilterBar, FilterExtras } from "../../../components/common/FilterBar";
import { useSupplierOptions } from "../../suppliers/api";
import { useCategories } from "../../categories/api";
import { STOCK_TYPES } from "../../../api/types";
import type { StockStatus } from "../../../api/types";
import type { ListParamsApi } from "../../../lib/useListParams";
import { INVENTORY_FILTER_KEYS } from "../filterKeys";

const STOCK_STATUS: readonly { value: StockStatus; label: string }[] = [
  { value: "all", label: "All" },
  { value: "low", label: "Low" },
  { value: "out", label: "Out" },
  { value: "ok", label: "OK" },
];

export function InventoryFilters({ params }: { params: ListParamsApi }) {
  const suppliers = useSupplierOptions();
  const categories = useCategories();

  const missingSupplier = params.get("has_supplier") === "false";
  const status = (params.get("stock_status") || "all") as StockStatus;

  return (
    <FilterBar label="Inventory filters">
      <SearchInput
        label="Search inventory"
        placeholder="SKU, name or model"
        value={params.get("q")}
        onCommit={(q) => params.set({ q })}
      />

      <Select
        aria-label="Supplier"
        value={params.get("supplier_id")}
        // Filtering by a named supplier and by "has no supplier" are mutually
        // exclusive questions; picking one answers the other.
        onChange={(e) => params.set({ supplier_id: e.target.value, has_supplier: null })}
      >
        <option value="">All suppliers</option>
        {(suppliers.data ?? []).map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </Select>

      <Select
        aria-label="Category"
        value={params.get("category_id")}
        onChange={(e) => params.set({ category_id: e.target.value })}
      >
        <option value="">All categories</option>
        {(categories.data ?? []).map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </Select>

      <Select
        aria-label="Item type"
        value={params.get("stock_type")}
        onChange={(e) => params.set({ stock_type: e.target.value })}
      >
        <option value="">All types</option>
        {STOCK_TYPES.map((t) => (
          <option key={t.value} value={t.value}>
            {t.label}
          </option>
        ))}
      </Select>

      <div className="w-full sm:w-auto sm:min-w-[240px]">
        <SegmentedControl
          label="Stock status"
          fullWidth
          value={status}
          options={STOCK_STATUS}
          onChange={(v) => params.set({ stock_status: v === "all" ? null : v })}
        />
      </div>

      <div className="w-full sm:ml-auto sm:w-auto">
        <FilterExtras>
          <Button
            size="sm"
            variant={missingSupplier ? "dark" : "ghost"}
            aria-pressed={missingSupplier}
            onClick={() =>
              params.set({
                has_supplier: missingSupplier ? null : "false",
                supplier_id: null,
              })
            }
          >
            <Icon name="alert" size={15} />
            Missing supplier
          </Button>

          <Button
            size="sm"
            variant="ghost"
            disabled={!params.hasFilters(INVENTORY_FILTER_KEYS)}
            onClick={() => params.clear(INVENTORY_FILTER_KEYS)}
            title="Clear all filters"
          >
            <Icon name="refresh" size={15} />
            Reset
          </Button>
        </FilterExtras>
      </div>
    </FilterBar>
  );
}
