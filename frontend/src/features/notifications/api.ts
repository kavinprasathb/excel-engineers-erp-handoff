import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

export type Severity = "critical" | "warning" | "info";
export type NotificationCategory = "quotes" | "orders" | "purchase_orders" | "inventory";

export interface NotificationItem {
  key: string;
  category: NotificationCategory;
  severity: Severity;
  title: string;
  detail: string;
  link: string;
  days: number | null;
}

export interface Notifications {
  total: number;
  counts: Record<Severity, number>;
  by_category: Partial<Record<NotificationCategory, number>>;
  items: NotificationItem[];
}

export const CATEGORY_LABEL: Record<NotificationCategory, string> = {
  quotes: "Quotations",
  orders: "Orders",
  purchase_orders: "Purchase orders",
  inventory: "Inventory",
};

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "Urgent",
  warning: "Attention",
  info: "Next step",
};

export const SEVERITY_COLOR: Record<Severity, string> = {
  critical: "var(--color-red)",
  warning: "var(--color-amber)",
  info: "#2a78d6",
};

/** Worked out live on the server; refreshed every few minutes and on focus. */
export function useNotifications() {
  return useQuery({
    meta: { silent: true },
    queryKey: ["notifications"],
    queryFn: ({ signal }) => api.get<Notifications>("/notifications", undefined, signal),
    refetchInterval: 5 * 60_000,
  });
}
