import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../../test/render";
import { LinesEditor } from "./LinesEditor";
import { OfferLayoutPicker } from "./OfferLayoutPicker";
import { suggestedLayout } from "../layouts";
import { draftFrom, emptyDraft, emptyLine, emptyNote, toCreate } from "../draft";
import type { Quotation } from "../../../api/types";

describe("Offer layouts", () => {
  it("spares: a group heading shows its subtotal and only the chosen columns are asked for", () => {
    const lines = [
      { ...emptyNote(), description: "Model: ETN SYT 080-065-160 EG" },
      { ...emptyLine(), description: "Shaft", quantity: "1", rate: "4475", product_id: 1 },
      { ...emptyLine(), description: "Mech seal", quantity: "1", rate: "10800", product_id: 2 },
      { ...emptyNote(), description: "Service" },
      { ...emptyLine(), description: "Service charges", quantity: "1", rate: "3500", product_id: 3 },
    ];
    renderWithProviders(
      <LinesEditor lines={lines} onChange={() => {}} errors={{}} readOnly={false} layout="spares" printColumns={["moc", "unit"]} />,
    );
    expect(screen.getAllByText("Group")).toHaveLength(2);
    expect(screen.getByText("₹15,275")).toBeInTheDocument();
    expect(screen.getByLabelText("Item 2 MOC")).toBeInTheDocument();
    expect(screen.queryByLabelText("Item 2 part number")).toBeNull();
    expect(screen.queryByLabelText("Item 2 scope of supply")).toBeNull();
  });

  it("pump offer: each pump asks for its datasheet values and scope of supply", () => {
    const rows = [{ key: "r1", section: "Duty", label: "Capacity (m³/hr)" }];
    renderWithProviders(
      <LinesEditor
        lines={[{ ...emptyLine(), description: "ETB 065-040-250 GG", product_id: 1 }]}
        onChange={() => {}}
        errors={{}}
        readOnly={false}
        layout="pump"
        datasheetRows={rows}
      />,
    );
    expect(screen.getByLabelText("Item 1 Capacity (m³/hr)")).toBeInTheDocument();
    expect(screen.getByLabelText("Item 1 scope of supply")).toBeInTheDocument();
  });

  it("the picker suggests a layout and is locked in a negotiation", async () => {
    const picked: string[] = [];
    const user = userEvent.setup();
    const { rerender } = renderWithProviders(
      <OfferLayoutPicker value="pump" suggested="spares" locked={false} onChange={(v) => picked.push(v)} />,
    );
    expect(screen.getByText("Suggested")).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: /Spares & Service/ }));
    expect(picked).toEqual(["spares"]);
    rerender(<OfferLayoutPicker value="pump" suggested="spares" locked onChange={(v) => picked.push(v)} />);
    expect(screen.getByRole("radio", { name: /Technical Sheet/ })).toBeDisabled();

    const four = Array.from({ length: 4 }, () => ({ ...emptyLine(), tech: { r: "25" } }));
    expect(suggestedLayout("pumps", four)).toBe("technical");
    expect(suggestedLayout("spares", [emptyLine()])).toBe("spares");
    expect(suggestedLayout("pumps", [emptyLine()])).toBe("pump");
  });

  it("round-trips the spares fields and print columns", () => {
    const d = emptyDraft();
    d.customer_id = "1";
    d.format = "spares";
    d.print_columns = ["part_no", "moc"];
    d.lines = [{ ...emptyLine(), description: "Shaft", rate: "10", part_no: "210", moc: "SS 410", delivery: "Ex stock" }];
    const out = toCreate(d, true);
    expect(out).toMatchObject({ format: "spares", print_columns: ["part_no", "moc"] });
    expect(out.lines[0]).toMatchObject({ part_no: "210", moc: "SS 410", delivery: "Ex stock", tech_values: [] });
    const back = draftFrom({
      format: "spares",
      print_columns: ["part_no", "moc"],
      tech_rows: [],
      scope: "",
      lines: [{ ...out.lines[0], id: 1, position: 0, value_paise: 0, deviations: [], components: [], service: "" }],
      terms: [],
      customer: { id: 1, name: "X" },
      customer_branch: null,
    } as unknown as Quotation);
    expect(back.print_columns).toEqual(["part_no", "moc"]);
    expect(back.lines[0]).toMatchObject({ part_no: "210", moc: "SS 410", delivery: "Ex stock" });
  });
});
