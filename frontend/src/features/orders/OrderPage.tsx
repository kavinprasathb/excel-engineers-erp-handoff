import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { Loading } from "../../components/ui/Spinner";
import { ErrorState } from "../../components/ui/ErrorState";
import { Modal } from "../../components/ui/Modal";
import { useToast } from "../../components/ui/toast-context";
import { errorMessage } from "../../lib/errors";
import { formatRupees, formatQuoteDate } from "../quotations/format";
import { useDeliverOrder, useOrder, useOrderPurchaseOrders, useRecheckOrder } from "./api";
import { OrderStatusBadge, PoStatusBadge } from "./badges";

/**
 * One order: each item with how many are held in stock and how many are
 * still to come, the purchase orders drafted for the shortfall, and — once
 * everything is in — Product Delivery.
 */
export default function OrderPage() {
  const { id } = useParams();
  const orderId = Number(id);
  const navigate = useNavigate();
  const toast = useToast();
  const order = useOrder(orderId);
  const pos = useOrderPurchaseOrders(orderId);
  const recheck = useRecheckOrder();
  const deliver = useDeliverOrder();
  const [confirm, setConfirm] = useState(false);

  if (order.isPending) {
    return (
      <>
        <PageHeader title="Order" />
        <PageBody>
          <Loading />
        </PageBody>
      </>
    );
  }
  if (order.isError) {
    return (
      <>
        <PageHeader title="Order" />
        <PageBody>
          <ErrorState title="Could not load this order" error={order.error} onRetry={() => order.refetch()} />
        </PageBody>
      </>
    );
  }
  const o = order.data;
  const short = o.lines.filter((l) => l.short > 0);

  return (
    <>
      <PageHeader
        title={o.number}
        description={`${o.customer.name} · accepted ${formatQuoteDate(o.created_at.slice(0, 10))}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <OrderStatusBadge status={o.status} />
            <Button onClick={() => navigate(`/quotations/${o.quotation_id}`)}>Quotation</Button>
            {o.status === "waiting_stock" ? (
              <Button
                loading={recheck.isPending}
                onClick={() =>
                  recheck.mutate(o.id, {
                    onSuccess: (r) =>
                      toast.success(
                        r.status === "ready"
                          ? "Everything is in stock — ready for Product Delivery."
                          : "Stock checked. Still waiting for some items.",
                      ),
                    onError: (e) => toast.error(errorMessage(e)),
                  })
                }
              >
                Check stock again
              </Button>
            ) : null}
            {o.status === "ready" ? (
              <Button variant="primary" onClick={() => setConfirm(true)}>
                Product Delivery
              </Button>
            ) : null}
          </div>
        }
      />
      <PageBody>
        <div className="space-y-4">
          {o.status === "waiting_stock" ? (
            <p className="rounded-md border border-amber/30 bg-amber-bg px-3 py-2 text-[13px] text-ink">
              Waiting for {short.length} of {o.lines.length} items. The order ships only when every
              item is in stock. What is already on the shelf is held for this order. When goods
              arrive, mark the purchase order as received (or add the stock in Inventory) and this
              order updates by itself.
            </p>
          ) : o.status === "ready" ? (
            <p className="rounded-md border border-line bg-hoverfill px-3 py-2 text-[13px] text-ink">
              Every item is in stock and held for this order. Press <b>Product Delivery</b> when it
              leaves the shop.
            </p>
          ) : (
            <p className="rounded-md border border-line bg-hoverfill px-3 py-2 text-[13px] text-ink">
              Delivered{o.delivered_at ? ` on ${formatQuoteDate(o.delivered_at.slice(0, 10))}` : ""}.
            </p>
          )}

          <Card>
            <CardHeader title="Items" description="How many of each are held in stock for this order." />
            <CardBody>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-[13px]">
                  <thead className="text-left text-[11px] font-medium uppercase tracking-wide text-ink-2">
                    <tr className="border-b border-line">
                      <th className="py-2 pr-3">Item</th>
                      <th className="px-3 py-2 text-right">Ordered</th>
                      <th className="px-3 py-2 text-right">In stock (held)</th>
                      <th className="px-3 py-2 text-right">To come</th>
                      <th className="py-2 pl-3 text-right">Rate</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {o.lines.map((l) => (
                      <tr key={l.id}>
                        <td className="py-2 pr-3">
                          <p className="text-ink">{l.description}</p>
                          <p className="text-[12px] text-ink-2">
                            {l.sku}
                            {l.set_description ? ` · part of “${l.set_description}”` : ""}
                          </p>
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums text-ink">{l.quantity}</td>
                        <td className="px-3 py-2 text-right tabular-nums text-ink">{l.reserved}</td>
                        <td
                          className={`px-3 py-2 text-right font-medium tabular-nums ${l.short > 0 && o.status !== "delivered" ? "text-amber" : "text-ink-2"}`}
                        >
                          {o.status === "delivered" ? "—" : l.short}
                        </td>
                        <td className="py-2 pl-3 text-right tabular-nums text-ink">
                          {l.set_description ? (l.value_paise ? `${formatRupees(l.value_paise)} (set)` : "In set") : formatRupees(l.rate_paise)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Purchase orders"
              description="Drafted automatically for what was not in stock, one per supplier."
            />
            <CardBody>
              {pos.isPending ? (
                <Loading />
              ) : (pos.data ?? []).length === 0 ? (
                <p className="text-[13px] text-ink-2">None needed — everything was in stock.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {(pos.data ?? []).map((p) => (
                    <li key={p.id} className="py-2">
                      <Link to={`/purchase-orders/${p.id}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md px-1 py-1 text-[13px] hover:bg-hoverfill">
                        <span className="font-medium tabular-nums text-ink">{p.number}</span>
                        <PoStatusBadge status={p.status} />
                        <span className={p.supplier ? "text-ink" : "text-amber"}>
                          {p.supplier ? p.supplier.name : "Supplier not set"}
                        </span>
                        <span className="text-ink-2">
                          {p.lines.map((ln) => `${ln.description} × ${ln.quantity}`).join(", ")}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </div>
      </PageBody>

      <Modal
        open={confirm}
        onClose={() => setConfirm(false)}
        title="Product Delivery"
        description="The held stock leaves the shop and the order is closed. This cannot be undone."
        footer={
          <>
            <Button onClick={() => setConfirm(false)}>Not yet</Button>
            <Button
              variant="primary"
              loading={deliver.isPending}
              onClick={() =>
                deliver.mutate(o.id, {
                  onSuccess: () => {
                    setConfirm(false);
                    toast.success(`${o.number} delivered.`);
                  },
                  onError: (e) => {
                    setConfirm(false);
                    toast.error(errorMessage(e));
                  },
                })
              }
            >
              Deliver now
            </Button>
          </>
        }
      >
        <ul className="space-y-1 text-[13px] text-ink">
          {o.lines.map((l) => (
            <li key={l.id}>
              {l.description} × {l.quantity}
            </li>
          ))}
        </ul>
      </Modal>
    </>
  );
}
