import type { InventoryRow } from "../../../api/types";

type Kind = "pump" | "valve" | "motor" | "seal" | "flange" | "tank" | "box";

/** Picks a glyph from the category (then the product) name. Never a photo. */
function productKind(row: Pick<InventoryRow, "name" | "category">): Kind {
  const text = `${row.category?.name ?? ""} ${row.name}`.toLowerCase();
  if (text.includes("pump")) return "pump";
  if (text.includes("valve")) return "valve";
  if (text.includes("motor")) return "motor";
  if (text.includes("seal")) return "seal";
  if (text.includes("flange")) return "flange";
  if (text.includes("tank")) return "tank";
  return "box";
}

const GLYPHS: Record<Kind, string[]> = {
  pump: [
    "M9 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10z",
    "M9 10.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z",
    "M7 7V4h4v3",
    "M14 11h2v2h-2zM16 9h5v6h-5z",
    "M3 19h18",
  ],
  valve: ["M3 9v6M21 9v6", "M3 12h4l5-3v6l-5-3M17 12h4M12 9l5 3-5 3", "M12 9V5M9 5h6"],
  motor: ["M5 7h11a3 3 0 0 1 3 3v4a3 3 0 0 1-3 3H5z", "M8 7v10M11 7v10M14 7v10", "M19 12h3", "M6 17v2M15 17v2"],
  seal: ["M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16z", "M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z"],
  flange: [
    "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
    "M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z",
    "M12 5.5v.01M12 18.5v.01M5.5 12h.01M18.5 12h.01",
  ],
  tank: ["M6 6c0-1.7 2.7-3 6-3s6 1.3 6 3v12c0 1.7-2.7 3-6 3s-6-1.3-6-3z", "M6 6c0 1.7 2.7 3 6 3s6-1.3 6-3", "M6 12c0 1.7 2.7 3 6 3s6-1.3 6-3"],
  box: ["M12 3l8 4.5v9L12 21l-8-4.5v-9z", "M4 7.5l8 4.5 8-4.5M12 12v9"],
};

const TINTS: Record<Kind, string> = {
  pump: "bg-brand/10 text-brand",
  valve: "bg-purple/10 text-purple",
  motor: "bg-green-bg text-green",
  seal: "bg-amber-bg text-amber",
  flange: "bg-brand/10 text-brand",
  tank: "bg-purple/10 text-purple",
  box: "bg-hoverfill text-ink-2",
};

export function ProductThumb({
  row,
  size = 36,
  className = "",
}: {
  row: Pick<InventoryRow, "name" | "category">;
  size?: number;
  className?: string;
}) {
  const kind = productKind(row);
  return (
    <span
      className={`grid shrink-0 place-items-center rounded-lg ${TINTS[kind]} ${className}`}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 24 24"
        width={size * 0.58}
        height={size * 0.58}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {GLYPHS[kind].map((d) => (
          <path key={d} d={d} />
        ))}
      </svg>
    </span>
  );
}

/** In stock / low / out, straight from the server's flags. */
export function StockStatusPill({ row }: { row: Pick<InventoryRow, "is_low_stock" | "is_out_of_stock"> }) {
  const [label, cls] = row.is_out_of_stock
    ? ["Out of Stock", "bg-red-bg text-red"]
    : row.is_low_stock
      ? ["Low Stock", "bg-amber-bg text-amber"]
      : ["In Stock", "bg-green-bg text-green"];
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[11.5px] font-semibold ${cls}`}>
      <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
      {label}
    </span>
  );
}
