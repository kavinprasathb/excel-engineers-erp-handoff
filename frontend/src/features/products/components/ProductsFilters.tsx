import { Select } from "../../../components/ui/Select";
import { Button } from "../../../components/ui/Button";
import { Icon } from "../../../components/ui/Icon";
import { SearchInput } from "../../../components/common/SearchInput";
import { FilterBar, FilterExtras } from "../../../components/common/FilterBar";
import { useSupplierOptions } from "../../suppliers/api";
import { useCategories } from "../../categories/api";
import type { ListParamsApi } from "../../../lib/useListParams";
import { PRODUCT_FILTER_KEYS } from "../filterKeys";

export function ProductsFilters({ params }: { params: ListParamsApi }) {
  const suppliers = useSupplierOptions();
  const categories = useCategories();

  const missingSupplier = params.get("has_supplier") === "false";

  return (
    <FilterBar label="Product filters">
      <SearchInput
        label="Search products"
        placeholder="SKU, name or model"
        value={params.get("q")}
        onCommit={(q) => params.set({ q })}
      />

      <Select
        aria-label="Supplier"
        value={params.get("supplier_id")}
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
        aria-label="Status"
        value={params.get("is_active")}
        onChange={(e) => params.set({ is_active: e.target.value })}
      >
        <option value="">All statuses</option>
        <option value="true">Active only</option>
        <option value="false">Inactive only</option>
      </Select>

      <div className="sm:col-span-2 lg:col-span-4">
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

          {params.hasFilters(PRODUCT_FILTER_KEYS) ? (
            <Button size="sm" onClick={() => params.clear(PRODUCT_FILTER_KEYS)}>
              Clear filters
            </Button>
          ) : null}
        </FilterExtras>
      </div>
    </FilterBar>
  );
}
