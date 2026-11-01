import { useState } from "react";
import { describe, expect, it } from "vitest";
import { fireEvent, screen, within } from "@testing-library/react";
import { renderWithProviders } from "../../../test/render";
import { LinesEditor } from "./LinesEditor";
import { deviationRows, emptyDraft, emptyLine, emptyNote, toCreate } from "../draft";
import type { DraftLine } from "../draft";

function Harness({ initial }: { initial: DraftLine[] }) {
  const [lines, setLines] = useState(initial);
  return <LinesEditor lines={lines} onChange={setLines} errors={{}} readOnly={false} />;
}

const two = (): DraftLine[] => [
  { ...emptyLine(), description: "A", quantity: "1", rate: "100" },
  { ...emptyLine(), description: "B", quantity: "1", rate: "50" },
];

describe("LinesEditor quantity", () => {
  it("quantity drives the line value and the total", () => {
    renderWithProviders(<Harness initial={two()} />);
    expect(screen.getByLabelText("Item 1 unit")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Item 1 quantity"), { target: { value: "3" } });
    expect(screen.getByText("₹300")).toBeInTheDocument();
    expect(screen.getByText("₹50")).toBeInTheDocument();
    expect(screen.getByText("₹350")).toBeInTheDocument();
    expect(screen.getByText("Total, excluding GST")).toBeInTheDocument();
  });

  it("sends the real quantity", () => {
    const d = emptyDraft();
    d.customer_id = "1";
    d.lines = [{ ...emptyLine(), product_id: 9, description: "Pump", quantity: "4", rate: "10" }];
    expect(toCreate(d, true).lines[0].quantity).toBe(4);
  });
});

describe("LinesEditor technical deviation", () => {
  it("sits under each item and edits only that item", () => {
    const lines: DraftLine[] = [
      { ...emptyLine([{ label: "Pump Model", value: "" }]), description: "A", rate: "100" },
      { ...emptyNote(), description: "KSB Make" },
      { ...emptyLine([{ label: "Pump Model", value: "" }]), description: "B", rate: "50" },
    ];
    renderWithProviders(<Harness initial={lines} />);
    const items = screen.getAllByRole("listitem").filter((li) => li.parentElement?.tagName === "OL");
    // Each product item carries its own panel; the note has none.
    expect(within(items[0]).getByText("Technical Deviation")).toBeInTheDocument();
    expect(within(items[1]).queryByText("Technical Deviation")).toBeNull();
    expect(within(items[2]).getByText("Technical Deviation")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Item 1 deviation Pump Model value"), {
      target: { value: "MCPK 125" },
    });
    expect(screen.getByLabelText("Item 1 deviation Pump Model value")).toHaveValue("MCPK 125");
    expect(screen.getByLabelText("Item 3 deviation Pump Model value")).toHaveValue("");
  });

  it("sends each line's own rows, and none for a note", () => {
    const d = emptyDraft();
    d.customer_id = "1";
    d.lines = [
      {
        ...emptyLine(),
        product_id: 9,
        description: "Pump",
        rate: "10",
        deviations: deviationRows([
          { label: " Pump Model ", value: " MCPK " },
          { label: "", value: "no label, dropped" },
        ]),
      },
      { ...emptyNote(), description: "KSB Make" },
    ];
    const out = toCreate(d, true).lines;
    expect(out[0].deviations).toEqual([{ label: "Pump Model", value: "MCPK" }]);
    expect(out[1].deviations).toEqual([]);
  });
});

describe("LinesEditor in a negotiation", () => {
  it("changes prices only: the rate is editable, nothing else is", () => {
    renderWithProviders(
      <LinesEditor lines={two()} onChange={() => {}} errors={{}} readOnly={false} priceOnly />,
    );
    expect(screen.getByLabelText("Item 1 rate")).not.toHaveAttribute("readonly");
    expect(screen.getByLabelText("Item 1 quantity")).toHaveAttribute("readonly");
    expect(screen.getByLabelText("Item 1 description")).toHaveAttribute("readonly");
    expect(screen.queryByRole("button", { name: /free-text line/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /remove item 1/i })).toBeNull();
  });
});
