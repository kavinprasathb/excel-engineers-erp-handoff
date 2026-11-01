/**
 * Inline SVG from a local path map.
 *
 * No icon package on purpose: lucide's default 2px stroke at 24px reads
 * noticeably heavier than the rest of the UI, and the 1.8/17 weight is part of
 * the look we ported. Everything below is a 24x24 viewBox scaled down, so the
 * stroke thins as it renders — which is exactly the effect we want.
 */

export const ICON_PATHS = {
  dashboard: ["M3 3h7v9H3z", "M14 3h7v5h-7z", "M14 12h7v9h-7z", "M3 16h7v5H3z"],
  quotations: [
    "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z",
    "M14 3v5h5",
    "M9 13h6",
    "M9 17h4",
  ],
  orders: [
    "M9 3h6v3H9z",
    "M15 4.5h2a2 2 0 0 1 2 2V19a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6.5a2 2 0 0 1 2-2h2",
    "M9 12h6",
    "M9 16h4",
  ],
  purchaseOrders: [
    "M3 6h10v10H3z",
    "M13 9h4l3 3v4h-7z",
    "M7.5 19a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z",
    "M17.5 19a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z",
  ],
  inventory: ["M12 3 3 7.5l9 4.5 9-4.5z", "M3 12l9 4.5 9-4.5", "M3 16.5 12 21l9-4.5"],
  products: [
    "M21 8 12 3 3 8v8l9 5 9-5z",
    "M3 8l9 5 9-5",
    "M12 13v8",
    "M7.5 5.5l9 5",
  ],
  suppliers: [
    "M3 21h18",
    "M5 21V8l6-4v17",
    "M11 21V11l8-3v13",
    "M8 12h.01",
    "M8 16h.01",
    "M15 13h.01",
    "M15 17h.01",
  ],
  customers: [
    "M16 20v-1.5a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4V20",
    "M9 10.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z",
    "M22 20v-1.5a4 4 0 0 0-3-3.87",
    "M16 3.75a4 4 0 0 1 0 7.5",
  ],
  settings: [
    "M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z",
    "M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1.04 1.56V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.56 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.56-1.04H3a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 4.66 8.9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34H9a1.7 1.7 0 0 0 1-1.56V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1.04 1.56 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87V9a1.7 1.7 0 0 0 1.56 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
  ],
  chevronLeft: ["M15 18l-6-6 6-6"],
  chevronRight: ["M9 18l6-6-6-6"],
  chevronDown: ["M6 9l6 6 6-6"],
  chevronUp: ["M18 15l-6-6-6 6"],
  menu: ["M3 6h18", "M3 12h18", "M3 18h18"],
  close: ["M18 6 6 18", "M6 6l12 12"],
  check: ["M20 6 9 17l-5-5"],
  search: ["M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z", "M21 21l-4.3-4.3"],
  plus: ["M12 5v14", "M5 12h14"],
  alert: ["M12 9v4", "M12 17h.01", "M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"],
  info: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z", "M12 16v-4", "M12 8h.01"],
  refresh: ["M3 12a9 9 0 0 1 15.5-6.2L21 8", "M21 3v5h-5", "M21 12a9 9 0 0 1-15.5 6.2L3 16", "M3 21v-5h5"],
  logout: ["M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4", "M16 17l5-5-5-5", "M21 12H9"],
  sun: [
    "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z",
    "M12 1v2", "M12 21v2", "M4.2 4.2l1.4 1.4", "M18.4 18.4l1.4 1.4",
    "M1 12h2", "M21 12h2", "M4.2 19.8l1.4-1.4", "M18.4 5.6l1.4-1.4",
  ],
  moon: ["M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"],
  monitor: ["M3 4h18v12H3z", "M8 20h8", "M12 16v4"],
  user: ["M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2", "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z"],
  inbox: [
    "M22 12h-6l-2 3h-4l-2-3H2",
    "M5.5 5.1 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.7 4H7.3a2 2 0 0 0-1.8 1.1z",
  ],
  panel: ["M3 4h18v16H3z", "M9 4v16"],
  lock: ["M5 11h14v10H5z", "M8 11V7a4 4 0 1 1 8 0v4"],
  bell: ["M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9", "M10.3 21a1.94 1.94 0 0 0 3.4 0"],
  chart: ["M3 3v18h18", "M7 16v-4", "M12 16V8", "M17 16v-7"],
  building: ["M3 21h18", "M5 21V4a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v17", "M9 8h2", "M13 8h2", "M9 12h2", "M13 12h2", "M10 21v-4h4v4"],
} as const;

export type IconName = keyof typeof ICON_PATHS;
