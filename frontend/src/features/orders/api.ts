import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { BranchRef, Page, Ref } from "../../api/types";

export type OrderStatus = "waiting_stock" | "ready" | "delivered";
export type PurchaseOrderStatus = "draft" | "sent" | "received";

export interface OrderLine {
  id: number;
  product_id: number;
  sku: string;
  description: string;
  quantity: number;
  /** Held in stock for this order. */
  reserved: number;
  /** Still to come in. */
  short: number;
  rate_paise: number;
  /** quantity x rate; for an item of a set, the set's value on its first item and 0 on the rest. */
  value_paise: number;
  /** For an item of a set: the set as quoted. */
  set_description: string;
}

export interface Order {
  id: number;
  number: string;
  status: OrderStatus;
  quotation_id: number;
  quotation_number: string;
  customer: Ref;
  delivered_at: string | null;
  created_at: string;
  total_paise: number;
  lines: OrderLine[];
}

export interface PurchaseOrder {
  id: number;
  number: string;
  status: PurchaseOrderStatus;
  supplier: Ref | null;
  /** The supplier's branch it goes to; null is the head office. */
  supplier_branch: BranchRef | null;
  order_id: number | null;
  created_at: string;
  received_at: string | null;
  lines: {
    id: number;
    product_id: number;
    description: string;
    quantity: number;
    /** null for staff: it is the purchase cost. */
    rate_paise: number | null;
    gst_rate_bp: number;
  }[];
}

export const ORDER_STATUS_LABEL: Record<OrderStatus, string> = {
  waiting_stock: "Waiting for stock",
  ready: "Ready for Product Delivery",
  delivered: "Delivered",
};

export const PO_STATUS_LABEL: Record<PurchaseOrderStatus, string> = {
  draft: "Draft",
  sent: "Sent to supplier",
  received: "Received",
};

const keys = {
  all: ["orders"] as const,
  list: (p: object) => ["orders", "list", p] as const,
  detail: (id: number) => ["orders", "detail", id] as const,
  pos: (id: number) => ["orders", "pos", id] as const,
  forQuote: (id: number) => ["orders", "quote", id] as const,
  poAll: ["purchase-orders"] as const,
  poList: (p: object) => ["purchase-orders", "list", p] as const,
  poDetail: (id: number) => ["purchase-orders", "detail", id] as const,
};

export function useOrders(params: { q?: string; status?: OrderStatus; page?: number }) {
  return useQuery({
    meta: { silent: true },
    queryKey: keys.list(params),
    queryFn: ({ signal }) => api.get<Page<Order>>("/orders", { ...params }, signal),
  });
}

export function useOrder(id: number) {
  return useQuery({
    meta: { silent: true },
    queryKey: keys.detail(id),
    queryFn: ({ signal }) => api.get<Order>(`/orders/${id}`, undefined, signal),
  });
}

export function useOrderPurchaseOrders(id: number) {
  return useQuery({
    meta: { silent: true },
    queryKey: keys.pos(id),
    queryFn: ({ signal }) => api.get<PurchaseOrder[]>(`/orders/${id}/purchase-orders`, undefined, signal),
  });
}

/** The order made when this quotation was accepted; 404 when there is none. */
export function useOrderForQuotation(quotationId: number, enabled: boolean) {
  return useQuery({
    meta: { silent: true },
    enabled,
    retry: false,
    queryKey: keys.forQuote(quotationId),
    queryFn: ({ signal }) => api.get<Order>(`/quotations/${quotationId}/order`, undefined, signal),
  });
}

function useInvalidate() {
  const client = useQueryClient();
  return () => {
    client.invalidateQueries({ queryKey: keys.all });
    client.invalidateQueries({ queryKey: keys.poAll });
    client.invalidateQueries({ queryKey: ["inventory"] });
    client.invalidateQueries({ queryKey: ["quotations"] });
  };
}

export function useCreateOrderForQuotation() {
  const done = useInvalidate();
  return useMutation({
    meta: { silent: true },
    mutationFn: (quotationId: number) => api.post<Order>(`/quotations/${quotationId}/order`),
    onSuccess: done,
  });
}

export function useRecheckOrder() {
  const done = useInvalidate();
  return useMutation({
    meta: { silent: true },
    mutationFn: (id: number) => api.post<Order>(`/orders/${id}/recheck`),
    onSuccess: done,
  });
}

export function useDeliverOrder() {
  const done = useInvalidate();
  return useMutation({
    meta: { silent: true },
    mutationFn: (id: number) => api.post<Order>(`/orders/${id}/deliver`),
    onSuccess: done,
  });
}

export function usePurchaseOrders(params: { q?: string; status?: PurchaseOrderStatus; page?: number }) {
  return useQuery({
    meta: { silent: true },
    queryKey: keys.poList(params),
    queryFn: ({ signal }) => api.get<Page<PurchaseOrder>>("/purchase-orders", { ...params }, signal),
  });
}

export function usePurchaseOrder(id: number) {
  return useQuery({
    meta: { silent: true },
    queryKey: keys.poDetail(id),
    queryFn: ({ signal }) => api.get<PurchaseOrder>(`/purchase-orders/${id}`, undefined, signal),
  });
}

export function useSetPoSupplier() {
  const done = useInvalidate();
  return useMutation({
    meta: { silent: true },
    mutationFn: ({
      id,
      supplierId,
      branchId,
    }: {
      id: number;
      supplierId: number;
      branchId: number | null;
    }) =>
      api.post<PurchaseOrder>(`/purchase-orders/${id}/supplier`, {
        supplier_id: supplierId,
        branch_id: branchId,
      }),
    onSuccess: done,
  });
}

export function useMarkPoSent() {
  const done = useInvalidate();
  return useMutation({
    meta: { silent: true },
    mutationFn: (id: number) => api.post<PurchaseOrder>(`/purchase-orders/${id}/sent`),
    onSuccess: done,
  });
}

export function useMarkPoReceived() {
  const done = useInvalidate();
  return useMutation({
    meta: { silent: true },
    mutationFn: (id: number) => api.post<PurchaseOrder>(`/purchase-orders/${id}/received`),
    onSuccess: done,
  });
}

/** The PDF is served on the session cookie, so a plain navigation is enough. */
export function purchaseOrderPdfUrl(id: number): string {
  return `/api/purchase-orders/${id}/pdf`;
}
