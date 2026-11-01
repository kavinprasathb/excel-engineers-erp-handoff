import { Select } from "../../../components/ui/Select";
import { Button } from "../../../components/ui/Button";
import { SearchInput } from "../../../components/common/SearchInput";
import { FilterBar, FilterExtras } from "../../../components/common/FilterBar";
import type { ListParamsApi } from "../../../lib/useListParams";
import { CUSTOMER_FILTER_KEYS } from "../filterKeys";

export function CustomersFilters({ params }: { params: ListParamsApi }) {
  return (
    <FilterBar label="Customer filters">
      <SearchInput
        label="Search customers"
        // The contract searches name and billing city only; promising GSTIN
        // here would be a placeholder that lies.
        placeholder="Name or city"
        value={params.get("q")}
        onCommit={(q) => params.set({ q })}
      />

      <Select
        aria-label="Status"
        value={params.get("is_active")}
        onChange={(e) => params.set({ is_active: e.target.value })}
      >
        <option value="">All customers</option>
        <option value="true">Active only</option>
        <option value="false">Inactive only</option>
      </Select>

      <div className="sm:col-span-2 lg:col-span-4">
        <FilterExtras>
          {params.hasFilters(CUSTOMER_FILTER_KEYS) ? (
            <Button size="sm" onClick={() => params.clear(CUSTOMER_FILTER_KEYS)}>
              Clear filters
            </Button>
          ) : (
            <p className="text-[13px] text-ink-2">Showing every customer.</p>
          )}
        </FilterExtras>
      </div>
    </FilterBar>
  );
}
