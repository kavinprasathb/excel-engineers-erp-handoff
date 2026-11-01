import { useNavigate } from "react-router-dom";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { DataList } from "../../components/ui/DataList";
import type { Column } from "../../components/ui/DataList";
import { Pagination } from "../../components/ui/Pagination";
import { Select } from "../../components/ui/Select";
import { Button } from "../../components/ui/Button";
import { ListStatus } from "../../components/common/ListStatus";
import { SearchInput } from "../../components/common/SearchInput";
import { FilterBar, FilterExtras } from "../../components/common/FilterBar";
import { useListParams } from "../../lib/useListParams";
import { formatRupees, formatQuoteDate } from "../quotations/format";
import { PO_STATUS_LABEL, usePurchaseOrders } from "./api";
import type { PurchaseOrder, PurchaseOrderStatus } from "./api";
import { PoStatusBadge } from "./badges";

const STATUSES = Object.keys(PO_STATUS_LABEL) as PurchaseOrderStatus[];
const KEYS = ["q", "status"] as const;

/** Purchase orders drafted for stock an order is waiting on. */
export default function PurchaseOrdersPage() {
  const navigate = useNavigate();
  const params = useListParams();
  const status = STATUSES.find((s) => s === params.get("status"));
  const pos = usePurchaseOrders({ q: params.get("q") || undefined, status, page: params.page });

  const columns: readonly Column<PurchaseOrder>[] = [
    { key: "number", header: "Purchase order", primary: true, cell: (p) => <span className="font-medium text-ink">{p.number}</span> },
    {
      key: "supplier",
      header: "Supplier",
      cell: (p) => (p.supplier ? p.supplier.name : <span className="text-amber">Supplier not set</span>),
    },
    { key: "items", header: "Items", cell: (p) => p.lines.map((l) => `${l.description} × ${l.quantity}`).join(", ") },
    { key: "date", header: "Drafted", cell: (p) => formatQuoteDate(p.created_at.slice(0, 10)) },
    {
      key: "value",
      header: "Value (at cost)",
      numeric: true,
      cell: (p) =>
        p.lines.some((l) => l.rate_paise === null)
          ? "—"
          : formatRupees(p.lines.reduce((s, l) => s + l.quantity * (l.rate_paise ?? 0), 0)),
    },
    { key: "status", header: "Status", secondary: true, cell: (p) => <PoStatusBadge status={p.status} /> },
  ];

  const data = pos.data;
  const filtered = params.hasFilters(KEYS);

  return (
    <>
      <PageHeader
        title="Purchase Orders"
        description="Drafted automatically for items an order is waiting on, one per supplier."
      />
      <PageBody>
        <FilterBar label="Purchase order filters">
          <SearchInput
            label="Search purchase orders"
            placeholder="PO number or supplier"
            value={params.get("q")}
            onCommit={(q) => params.set({ q })}
          />
          <Select aria-label="Status" value={params.get("status")} onChange={(e) => params.set({ status: e.target.value })}>
            <option value="">Any status</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {PO_STATUS_LABEL[s]}
              </option>
            ))}
          </Select>
          <div className="sm:col-span-2 lg:col-span-4">
            <FilterExtras>
              {filtered ? (
                <Button size="sm" onClick={() => params.clear(KEYS)}>
                  Clear filters
                </Button>
              ) : null}
            </FilterExtras>
          </div>
        </FilterBar>
        <DataList
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(p) => p.id}
          onRowClick={(p) => navigate(`/purchase-orders/${p.id}`)}
          message={
            <ListStatus
              isPending={pos.isPending}
              isError={pos.isError}
              error={pos.error}
              onRetry={() => pos.refetch()}
              errorTitle="Could not load purchase orders"
              emptyIcon="purchaseOrders"
              emptyTitle={filtered ? "Nothing matches this filter" : "No purchase orders yet"}
              emptyDescription={
                filtered
                  ? "Try a different search, or clear the filters."
                  : "One is drafted when an accepted quotation needs stock the shop does not have."
              }
            />
          }
        />
        {data && data.total > 0 ? (
          <div className="mt-3">
            <Pagination page={data.page} pages={data.pages} total={data.total} pageSize={data.page_size} onPageChange={params.setPage} />
          </div>
        ) : null}
      </PageBody>
    </>
  );
}
