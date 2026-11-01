import { useState } from "react";
import { describe, expect, it } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../../test/render";
import { TechSheetEditor } from "./TechSheetEditor";
import { draftFrom, emptyDraft, emptyLine, toCreate } from "../draft";
import type { DraftLine, DraftTechRow } from "../draft";
import type { Quotation } from "../../../api/types";

let lastRows: DraftTechRow[] = [];

function Harness({ priceOnly = false }: { priceOnly?: boolean }) {
  const [rows, setRows] = useState<DraftTechRow[]>([]);
  const [lines, setLines] = useState<DraftLine[]>([
    { ...emptyLine(), description: "ETN 100-80-160", quantity: "2", rate: "164300" },
    { ...emptyLine(), description: "ETN 65-40-160", quantity: "2", rate: "104400" },
  ]);
  const [scope, setScope] = useState("");
  // Recorded on change, not during render: what the editor last handed back.
  function onRows(next: DraftTechRow[]) {
    lastRows = next;
    setRows(next);
  }
  return (
    <TechSheetEditor
      rows={rows}
      lines={lines}
      scope={scope}
      onRows={onRows}
      onLines={setLines}
      onScope={setScope}
      errors={{}}
      readOnly={false}
      priceOnly={priceOnly}
    />
  );
}

describe("TechSheetEditor", () => {
  it("fills rows from a template, copies a value across and totals each column", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness />);
    await user.selectOptions(screen.getByLabelText("Rows from template"), "End suction pump");
    expect(lastRows.map((r) => r.label)).toContain("NPSH R (m)");
    expect(screen.getByText("Material Of Construction")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Column 1 Liquid Handled"), { target: { value: "Water" } });
    await user.click(screen.getByRole("button", { name: "Copy row 1 to all columns" }));
    expect(screen.getByLabelText("Column 2 Liquid Handled")).toHaveValue("Water");

    // Unit price x qty per column.
    expect(screen.getByText("₹3,28,600")).toBeInTheDocument();
    expect(screen.getByText("₹2,08,800")).toBeInTheDocument();
  });

  it("a negotiation changes unit prices only", () => {
    renderWithProviders(<Harness priceOnly />);
    expect(screen.queryByLabelText("Rows from template")).toBeNull();
    expect(screen.getByLabelText("Column 1 quantity")).toHaveAttribute("readonly");
    expect(screen.getByLabelText("Column 1 pump model")).toHaveAttribute("readonly");
    expect(screen.getByLabelText("Column 1 unit price")).not.toHaveAttribute("readonly");
  });

  it("round-trips: values are saved in row order and loaded back by row", () => {
    const d = emptyDraft();
    d.customer_id = "1";
    d.format = "technical";
    d.tech_rows = [
      { key: "a", section: "Duty", label: "Capacity" },
      { key: "b", section: "Duty", label: "Head" },
    ];
    d.lines = [{ ...emptyLine(), description: "ETN", rate: "100", service: "UF Feed", tech: { b: "30", a: "38" } }];
    const out = toCreate(d, true);
    expect(out.format).toBe("technical");
    expect(out.tech_rows).toEqual([
      { section: "Duty", label: "Capacity" },
      { section: "Duty", label: "Head" },
    ]);
    expect(out.lines[0]).toMatchObject({ service: "UF Feed", tech_values: ["38", "30"] });

    const back = draftFrom({
      format: "technical",
      tech_rows: out.tech_rows,
      scope: "",
      lines: [{ ...out.lines[0], id: 1, position: 0, value_paise: 0, deviations: [], components: [] }],
      terms: [],
      customer: { id: 1, name: "X" },
      customer_branch: null,
    } as unknown as Quotation);
    const [capacity, head] = back.tech_rows;
    expect(back.lines[0].tech[capacity.key]).toBe("38");
    expect(back.lines[0].tech[head.key]).toBe("30");
  });
});
