import { Select } from "../../../components/ui/Select";
import { Button } from "../../../components/ui/Button";
import { SearchInput } from "../../../components/common/SearchInput";
import { FilterBar, FilterExtras } from "../../../components/common/FilterBar";
import type { ListParamsApi } from "../../../lib/useListParams";
import { SUPPLIER_FILTER_KEYS } from "../filterKeys";

export function SuppliersFilters({ params }: { params: ListParamsApi }) {
  return (
    <FilterBar label="Supplier filters">
      <SearchInput
        label="Search suppliers"
        placeholder="Name, city or GSTIN"
        value={params.get("q")}
        onCommit={(q) => params.set({ q })}
      />

      <Select
        aria-label="Status"
        value={params.get("is_active")}
        onChange={(e) => params.set({ is_active: e.target.value })}
      >
        <option value="">All suppliers</option>
        <option value="true">Active only</option>
        <option value="false">Inactive only</option>
      </Select>

      <div className="sm:col-span-2 lg:col-span-4">
        <FilterExtras>
          {params.hasFilters(SUPPLIER_FILTER_KEYS) ? (
            <Button size="sm" onClick={() => params.clear(SUPPLIER_FILTER_KEYS)}>
              Clear filters
            </Button>
          ) : (
            <p className="text-[13px] text-ink-2">Showing every supplier.</p>
          )}
        </FilterExtras>
      </div>
    </FilterBar>
  );
}
