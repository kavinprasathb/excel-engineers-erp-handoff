import { Select } from "../../../components/ui/Select";
import { Button } from "../../../components/ui/Button";
import { SearchInput } from "../../../components/common/SearchInput";
import { FilterBar, FilterExtras } from "../../../components/common/FilterBar";
import { QUOTATION_STATUSES, QUOTATION_TYPES } from "../../../api/types";
import type { ListParamsApi } from "../../../lib/useListParams";
import { QUOTATION_FILTER_KEYS } from "../filterKeys";
import { STATUS_LABEL } from "../format";

export function QuotationsFilters({ params }: { params: ListParamsApi }) {
  return (
    <FilterBar label="Quotation filters">
      <SearchInput
        label="Search quotations"
        placeholder="Number, subject or customer"
        value={params.get("q")}
        onCommit={(q) => params.set({ q })}
      />

      <Select
        aria-label="Type"
        value={params.get("type")}
        onChange={(e) => params.set({ type: e.target.value })}
      >
        <option value="">All types</option>
        {QUOTATION_TYPES.map((t) => (
          <option key={t.value} value={t.value}>
            {t.label} ({t.prefix})
          </option>
        ))}
      </Select>

      <Select
        aria-label="Status"
        value={params.get("status")}
        onChange={(e) => params.set({ status: e.target.value })}
      >
        <option value="">Any status</option>
        {QUOTATION_STATUSES.map((s) => (
          <option key={s} value={s}>
            {STATUS_LABEL[s]}
          </option>
        ))}
      </Select>

      <div className="sm:col-span-2 lg:col-span-4">
        <FilterExtras>
          {params.hasFilters(QUOTATION_FILTER_KEYS) ? (
            <Button size="sm" onClick={() => params.clear(QUOTATION_FILTER_KEYS)}>
              Clear filters
            </Button>
          ) : (
            <p className="text-[13px] text-ink-2">One row per number, newest first.</p>
          )}
        </FilterExtras>
      </div>
    </FilterBar>
  );
}
