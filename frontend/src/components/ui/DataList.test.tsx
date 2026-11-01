import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Column } from "./DataList";
import { DataList } from "./DataList";
import { EmptyState } from "./EmptyState";

interface Row {
  id: number;
  sku: string;
  name: string;
  available: number;
}

const rows: Row[] = [
  { id: 12, sku: "KSB-ETA-65-200", name: "KSB Etanorm 65-200", available: 9 },
  { id: 13, sku: "CRI-MB-15", name: "CRI MB 15", available: 0 },
];

const columns: Column<Row>[] = [
  { key: "name", header: "Product", cell: (r) => r.name, primary: true },
  { key: "sku", header: "SKU", cell: (r) => r.sku, secondary: true },
  { key: "available", header: "Available", cell: (r) => r.available, numeric: true },
];

describe("DataList", () => {
  it("renders the same rows twice — a table for md+, cards for phones", () => {
    const { container } = render(
      <DataList columns={columns} rows={rows} rowKey={(r) => r.id} />,
    );

    // jsdom has no viewport-driven CSS, so the responsive contract is asserted
    // structurally: both renderings exist, and Tailwind's visibility classes
    // pick one. That is exactly the property that would regress if someone
    // deleted a branch.
    expect(screen.getAllByText("KSB Etanorm 65-200")).toHaveLength(2);

    const table = container.querySelector("table");
    expect(table).not.toBeNull();
    expect(table?.parentElement?.className).toContain("overflow-x-auto");
    expect(container.querySelector(".hidden.md\\:block")).not.toBeNull();
    expect(container.querySelector("ul.md\\:hidden")).not.toBeNull();
  });

  it("right-aligns numeric columns and keeps digits tabular", () => {
    const { container } = render(
      <DataList columns={columns} rows={rows} rowKey={(r) => r.id} />,
    );

    const cells = Array.from(container.querySelectorAll("td")).filter((td) =>
      td.className.includes("text-right"),
    );
    expect(cells.length).toBe(rows.length);
    expect(cells[0].className).toContain("tabular-nums");
  });

  it("shows the empty message instead of an empty table", () => {
    render(
      <DataList
        columns={columns}
        rows={[]}
        rowKey={(r) => r.id}
        message={<EmptyState title="No products match this filter" />}
      />,
    );

    expect(screen.getByText("No products match this filter")).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });
});
