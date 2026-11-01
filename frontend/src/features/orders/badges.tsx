import { Badge } from "../../components/ui/Badge";
import type { BadgeTone } from "../../components/ui/Badge";
import { ORDER_STATUS_LABEL, PO_STATUS_LABEL } from "./api";
import type { OrderStatus, PurchaseOrderStatus } from "./api";

const ORDER_TONE: Record<OrderStatus, BadgeTone> = {
  waiting_stock: "amber",
  ready: "brand",
  delivered: "green",
};

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  return <Badge tone={ORDER_TONE[status]}>{ORDER_STATUS_LABEL[status]}</Badge>;
}

export function PoStatusBadge({ status }: { status: PurchaseOrderStatus }) {
  const tone: BadgeTone = status === "received" ? "green" : status === "sent" ? "brand" : "gray";
  return <Badge tone={tone}>{PO_STATUS_LABEL[status]}</Badge>;
}
