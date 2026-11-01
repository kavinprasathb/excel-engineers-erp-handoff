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
import { ORDER_STATUS_LABEL, useOrders } from "./api";
import type { Order, OrderStatus } from "./api";
import { OrderStatusBadge } from "./badges";

const STATUSES = Object.keys(ORDER_STATUS_LABEL) as OrderStatus[];
const KEYS = ["q", "status"] as const;

/** Orders made from accepted quotations, and where each one stands. */
export default function OrdersPage() {
  const navigate = useNavigate();
  const params = useListParams();
  const status = STATUSES.find((s) => s === params.get("status"));
  const orders = useOrders({ q: params.get("q") || undefined, status, page: params.page });

  const columns: readonly Column<Order>[] = [
    {
      key: "number",
      header: "Order",
      primary: true,
      cell: (o) => (
        <div className="min-w-0">
          <p className="truncate font-medium text-ink">{o.number}</p>
          <p className="truncate text-[12px] text-ink-2">From {o.quotation_number}</p>
        </div>
      ),
    },
    { key: "customer", header: "Customer", cell: (o) => o.customer.name },
    {
      key: "items",
      header: "Stock",
      cell: (o) => {
        const short = o.lines.filter((l) => l.short > 0).length;
        return o.status === "delivered"
          ? "Delivered"
          : short === 0
            ? `All ${o.lines.length} items in stock`
            : `${short} of ${o.lines.length} items waiting`;
      },
    },
    { key: "date", header: "Accepted", cell: (o) => formatQuoteDate(o.created_at.slice(0, 10)) },
    { key: "total", header: "Value (ex-GST)", numeric: true, cell: (o) => formatRupees(o.total_paise) },
    { key: "status", header: "Status", secondary: true, cell: (o) => <OrderStatusBadge status={o.status} /> },
  ];

  const data = orders.data;
  const filtered = params.hasFilters(KEYS);

  return (
    <>
      <PageHeader
        title="Orders"
        description="Made automatically when a quotation is accepted. Stock is held for each order."
      />
      <PageBody>
        <FilterBar label="Order filters">
          <SearchInput
            label="Search orders"
            placeholder="Order number or customer"
            value={params.get("q")}
            onCommit={(q) => params.set({ q })}
          />
          <Select
            aria-label="Status"
            value={params.get("status")}
            onChange={(e) => params.set({ status: e.target.value })}
          >
            <option value="">Any status</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {ORDER_STATUS_LABEL[s]}
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
          rowKey={(o) => o.id}
          onRowClick={(o) => navigate(`/orders/${o.id}`)}
          message={
            <ListStatus
              isPending={orders.isPending}
              isError={orders.isError}
              error={orders.error}
              onRetry={() => orders.refetch()}
              errorTitle="Could not load orders"
              emptyIcon="orders"
              emptyTitle={filtered ? "Nothing matches this filter" : "No orders yet"}
              emptyDescription={
                filtered
                  ? "Try a different search, or clear the filters."
                  : "An order appears here as soon as a quotation is accepted."
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
      </PageBody>
    </>
  );
}
