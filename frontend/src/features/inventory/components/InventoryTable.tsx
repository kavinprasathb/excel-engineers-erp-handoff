import { DataList } from "../../../components/ui/DataList";
import type { Column } from "../../../components/ui/DataList";
import { Pagination } from "../../../components/ui/Pagination";
import { Button } from "../../../components/ui/Button";
import { ListStatus } from "../../../components/common/ListStatus";
import { formatNumber, orDash } from "../../../lib/format";
import { Icon } from "../../../components/ui/Icon";
import { useInventory } from "../api";
import { INVENTORY_FILTER_KEYS, inventoryListParams } from "../filterKeys";
import { ProductThumb, StockStatusPill } from "./ProductThumb";
import { SupplierCell } from "./SupplierCell";
import { AvailabilityCell } from "./AvailabilityCell";
import { stockTypeLabel } from "../../../api/types";
import type { InventoryRow } from "../../../api/types";
import type { ListParamsApi } from "../../../lib/useListParams";

export function InventoryTable({
  params,
  onAdjust,
  onHistory,
  selectedId,
  onSelect,
}: {
  params: ListParamsApi;
  onAdjust: (row: InventoryRow) => void;
  onHistory: (row: InventoryRow) => void;
  /** The row shown in the quick view, if any. */
  selectedId?: number | null;
  onSelect?: (row: InventoryRow) => void;
}) {
  const inventory = useInventory(inventoryListParams(params));
  const firstIndex = inventory.data ? (inventory.data.page - 1) * inventory.data.page_size : 0;
  const indexOf = new Map((inventory.data?.items ?? []).map((r, i) => [r.product_id, firstIndex + i + 1]));

  const columns: readonly Column<InventoryRow>[] = [
    {
      key: "index",
      header: "#",
      hideOnMobile: true,
      cell: (row) => <span className="tabular-nums text-ink-2">{indexOf.get(row.product_id)}</span>,
    },
    {
      key: "product",
      header: "Product / Item",
      primary: true,
      cell: (row) => (
        <div className="flex min-w-0 items-center gap-3">
          <ProductThumb
            row={row}
            className={selectedId === row.product_id ? "ring-2 ring-brand ring-offset-1 ring-offset-card" : ""}
          />
          <div className="min-w-0">
            <p className="truncate font-medium text-ink">{row.name}</p>
            <p className="truncate text-[12px] text-ink-2">
              {row.sku}
              {row.stock_type && row.stock_type !== "stocked" ? (
                <span
                  className={`ml-1.5 rounded-full px-1.5 py-px text-[11px] font-medium ${row.stock_type === "service" ? "bg-violet-100 text-violet-700" : "bg-amber-bg text-amber"}`}
                >
                  {stockTypeLabel(row.stock_type)}
                </span>
              ) : null}
            </p>
          </div>
        </div>
      ),
    },
    { key: "model", header: "Model", cell: (row) => orDash(row.model_number || null) },
    { key: "supplier", header: "Supplier", cell: (row) => <SupplierCell row={row} /> },
    { key: "category", header: "Category", cell: (row) => orDash(row.category?.name) },
    {
      key: "onHand",
      header: "On hand",
      numeric: true,
      cell: (row) => formatNumber(row.quantity_on_hand),
    },
    {
      key: "reserved",
      header: "Reserved",
      numeric: true,
      cell: (row) => formatNumber(row.quantity_reserved),
    },
    {
      key: "available",
      header: "Available",
      numeric: true,
      cell: (row) => <AvailabilityCell row={row} />,
    },
    {
      key: "status",
      header: "Status",
      secondary: true,
      cell: (row) => <StockStatusPill row={row} />,
    },
    {
      key: "actions",
      header: "Actions",
      cell: (row) => (
        <div className="flex flex-wrap gap-1.5">
          <Button size="sm" onClick={() => onAdjust(row)} title="Adjust stock" aria-label={`Adjust stock for ${row.name}`}>
            <Icon name="plus" size={14} />
            Adjust
          </Button>
          <Button size="sm" onClick={() => onHistory(row)} title="Stock history" aria-label={`History for ${row.name}`}>
            <Icon name="refresh" size={14} />
            History
          </Button>
        </div>
      ),
    },
  ];

  const data = inventory.data;
  const filtered = params.hasFilters(INVENTORY_FILTER_KEYS);

  return (
    <>
      <DataList
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(row) => row.product_id}
        onRowClick={onSelect}
        message={
          <ListStatus
            isPending={inventory.isPending}
            isError={inventory.isError}
            error={inventory.error}
            onRetry={() => inventory.refetch()}
            errorTitle="Could not load inventory"
            emptyIcon="inventory"
            emptyTitle={filtered ? "No products match this filter" : "No products yet"}
            emptyDescription={
              filtered
                ? "Try a different search, supplier or stock status, or clear the filters."
                : "Add a product, or import your catalogue, and its stock will appear here."
            }
          />
        }
      />

      {data && data.total > 0 ? (
        <div className="mt-3">
          <Pagination
            page={data.page}
            pages={data.pages}
            total={data.total}
            pageSize={data.page_size}
            onPageChange={params.setPage}
          />
        </div>
      ) : null}
    </>
  );
}
