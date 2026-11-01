import type { IconName } from "../ui/Icon";
import type { ArtName } from "./Art";

/** Which illustration stands in for a line icon on empty screens and summary boxes. */
export const ICON_ART: Partial<Record<IconName, ArtName>> = {
  products: "baseframe",
  inventory: "shelf",
  quotations: "quote",
  refresh: "negotiation",
  orders: "order",
  purchaseOrders: "clipboard",
  suppliers: "factory",
  customers: "building",
  chart: "chart",
  dashboard: "chart",
  bell: "bell",
  check: "check",
  inbox: "tray",
  lock: "lock",
  alert: "warning",
  user: "people",
};
