import { DataList } from "../../../components/ui/DataList";
import type { Column } from "../../../components/ui/DataList";
import { Pagination } from "../../../components/ui/Pagination";
import { Button } from "../../../components/ui/Button";
import { Badge } from "../../../components/ui/Badge";
import { Chip } from "../../../components/ui/Chip";
import { ListStatus } from "../../../components/common/ListStatus";
import { bpToPercent, formatMoney, formatNumber, orDash } from "../../../lib/format";
import { useProducts } from "../api";
import { PRODUCT_FILTER_KEYS } from "../filterKeys";
import type { Product } from "../../../api/types";
import type { ListParamsApi } from "../../../lib/useListParams";
import { useIsOwner } from "../../auth/api";

export function ProductsTable({
  params,
  onEdit,
  onDelete,
  onCreate,
}: {
  params: ListParamsApi;
  onEdit: (product: Product) => void;
  onDelete: (product: Product) => void;
  onCreate: () => void;
}) {
  const owner = useIsOwner();
  const activeRaw = params.get("is_active");
  const hasSupplierRaw = params.get("has_supplier");
  const products = useProducts({
    q: params.get("q") || undefined,
    supplier_id: params.getNumber("supplier_id"),
    category_id: params.getNumber("category_id"),
    is_active: activeRaw === "" ? null : activeRaw === "true",
    has_supplier: hasSupplierRaw === "" ? null : hasSupplierRaw === "true",
    page: params.page,
  });

  const columns: readonly Column<Product>[] = [
    {
      key: "product",
      header: "Product",
      primary: true,
      cell: (p) => (
        <div className="min-w-0">
          <p className="truncate font-medium text-ink">{p.name}</p>
          <p className="truncate text-[12px] text-ink-2">
            {p.sku}
            {p.model_number ? " · " + p.model_number : ""}
          </p>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      secondary: true,
      cell: (p) => (p.is_active ? null : <Badge tone="gray">Inactive</Badge>),
    },
    {
      key: "supplier",
      header: "Supplier",
      cell: (p) =>
        p.supplier ? (
          p.supplier.name
        ) : (
          // Same amber signal as Inventory, but read-only here: fixing it in
          // place belongs on the screen built around that job.
          <Chip tone="amber">No supplier</Chip>
        ),
    },
    { key: "category", header: "Category", cell: (p) => orDash(p.category?.name) },
    {
      key: "purchase",
      header: "Cost",
      numeric: true,
      cell: (p) => (p.purchase_cost === null ? "—" : formatMoney(p.purchase_cost)),
      hideOnMobile: true,
    },
    { key: "sell", header: "Price", numeric: true, cell: (p) => formatMoney(p.sell_price) },
    {
      key: "gst",
      header: "GST",
      numeric: true,
      cell: (p) => bpToPercent(p.gst_rate_bp) + "%",
    },
    { key: "hsn", header: "HSN", cell: (p) => orDash(p.hsn_code), hideOnMobile: true },
    {
      key: "available",
      header: "Available",
      numeric: true,
      // Straight from the server; the client never subtracts reserved itself.
      cell: (p) => formatNumber(p.inventory.quantity_available),
    },
    {
      key: "actions",
      header: "Actions",
      cell: (p) => (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={() => onEdit(p)}>
            Edit
          </Button>
          {owner ? (
          <Button size="sm" onClick={() => onDelete(p)} disabled={!p.is_active}>
            Deactivate
          </Button>) : null}
        </div>
      ),
    },
  ];

  const data = products.data;
  const filtered = params.hasFilters(PRODUCT_FILTER_KEYS);

  return (
    <>
      <DataList
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(p) => p.id}
        message={
          <ListStatus
            isPending={products.isPending}
            isError={products.isError}
            error={products.error}
            onRetry={() => products.refetch()}
            errorTitle="Could not load products"
            emptyIcon="products"
            emptyTitle={filtered ? "No products match this filter" : "No products yet"}
            emptyDescription={
              filtered
                ? "Try a different search, supplier or category, or clear the filters."
                : "Add a product, or import your existing catalogue from a spreadsheet."
            }
            emptyAction={
              filtered ? null : (
                <Button variant="primary" size="sm" onClick={onCreate}>
                  New product
                </Button>
              )
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
