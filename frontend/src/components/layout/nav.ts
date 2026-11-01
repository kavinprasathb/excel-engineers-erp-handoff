import type { IconName } from "../ui/Icon";

export interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  /**
   * False means the route renders a "Coming soon" placeholder. The item still
   * appears: the nav is how the owner sees what the product will be, and
   * hiding half of it would make the app look smaller than it is.
   */
  ready: boolean;
  /** The heading the item sits under; consecutive items share one heading. */
  group: string;
  /** Only the owner sees it; staff get a plain "owner only" page if they type the address. */
  ownerOnly?: boolean;
  /** False: reachable (top bar, quick jump) but not listed in the sidebar. */
  sidebar?: boolean;
}

/** Pinned to the bottom of the sidebar, under the daily work. */
export const BOTTOM_GROUP = "Administration";

export const NAV_ITEMS: readonly NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: "dashboard", ready: true, group: "Overview" },
  // Lives on the bell in the top bar.
  { to: "/notifications", label: "Notifications", icon: "bell", ready: true, group: "Overview", sidebar: false },
  { to: "/quotations", label: "Quotations", icon: "quotations", ready: true, group: "Sales" },
  { to: "/revised-quotations", label: "Revised Quotations", icon: "panel", ready: true, group: "Sales" },
  { to: "/negotiations", label: "Negotiations", icon: "refresh", ready: true, group: "Sales" },
  { to: "/orders", label: "Orders", icon: "orders", ready: true, group: "Orders & Buying" },
  { to: "/purchase-orders", label: "Purchase Orders", icon: "purchaseOrders", ready: true, group: "Orders & Buying" },
  { to: "/inventory", label: "Inventory", icon: "inventory", ready: true, group: "Stock" },
  { to: "/products", label: "Products", icon: "products", ready: true, group: "Stock" },
  { to: "/customers", label: "Customers", icon: "customers", ready: true, group: "Contacts" },
  { to: "/suppliers", label: "Suppliers", icon: "suppliers", ready: true, group: "Contacts" },
  { to: "/analytics", label: "Analytics", icon: "chart", ready: true, group: "Strategic Insights", ownerOnly: true },
  { to: "/quote-history", label: "Quote History", icon: "inbox", ready: true, group: "Strategic Insights" },
  { to: "/deal-tracker", label: "Deal Tracker", icon: "orders", ready: true, group: "Strategic Insights", ownerOnly: true },
  { to: "/staff", label: "Staff", icon: "user", ready: true, group: BOTTOM_GROUP, ownerOnly: true },
  { to: "/activity", label: "Activity Log", icon: "inbox", ready: true, group: BOTTOM_GROUP, ownerOnly: true },
  { to: "/settings", label: "Settings", icon: "settings", ready: true, group: BOTTOM_GROUP, ownerOnly: true },
];

/** Every page this person may open (the quick jump searches these). */
export function visibleItems(owner: boolean): readonly NavItem[] {
  return NAV_ITEMS.filter((i) => owner || !i.ownerOnly);
}

/** The sidebar's list, grouped in order: [group, items][]. */
export function sidebarGroups(owner: boolean): [string, NavItem[]][] {
  const out: [string, NavItem[]][] = [];
  for (const item of visibleItems(owner)) {
    if (item.sidebar === false) continue;
    const last = out[out.length - 1];
    if (last && last[0] === item.group) last[1].push(item);
    else out.push([item.group, [item]]);
  }
  return out;
}

/** The nav item a path belongs to, for the top bar's page name. */
export function itemForPath(pathname: string): NavItem | undefined {
  return NAV_ITEMS.find((i) => pathname === i.to || pathname.startsWith(`${i.to}/`));
}
