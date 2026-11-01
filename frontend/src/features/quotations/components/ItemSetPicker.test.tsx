import { useState } from "react";
import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { server } from "../../../test/server";
import { renderWithProviders } from "../../../test/render";
import { LinesEditor } from "./LinesEditor";
import { emptyDraft, emptyLine, toCreate } from "../draft";
import type { DraftLine } from "../draft";
import type { ProductLookup } from "../../../api/types";

const CATALOGUE: ProductLookup[] = [
  { id: 1, sku: "PMP", name: "Pump", model_number: "", unit: "Each", hsn_code: "8413", sell_price: 1000000, quantity_available: 4 },
  { id: 2, sku: "BF", name: "Pump Base Frame", model_number: "", unit: "Each", hsn_code: "", sell_price: 200000, quantity_available: 0 },
  { id: 3, sku: "CPL", name: "Coupling", model_number: "", unit: "Each", hsn_code: "", sell_price: 50000, quantity_available: 9 },
];

/** Every network call the editor makes, so a test can say "nothing touched stock". */
function serveCatalogue(calls: string[]) {
  server.use(
    http.get("/api/products/lookup", ({ request }) => {
      calls.push(`GET ${new URL(request.url).pathname}`);
      const q = (new URL(request.url).searchParams.get("q") ?? "").toLowerCase();
      return HttpResponse.json(CATALOGUE.filter((p) => p.name.toLowerCase().includes(q)));
    }),
    http.all("*", ({ request }) => {
      calls.push(`${request.method} ${new URL(request.url).pathname}`);
      return HttpResponse.json({});
    }),
  );
}

let last: DraftLine[] = [];

function Harness({ initial }: { initial: DraftLine[] }) {
  const [lines, setLines] = useState(initial);
  // Recorded on change, not during render: what the editor last handed back.
  function onChange(next: DraftLine[]) {
    last = next;
    setLines(next);
  }
  return <LinesEditor lines={lines} onChange={onChange} errors={{}} readOnly={false} />;
}

async function addItem(user: ReturnType<typeof userEvent.setup>, name: string) {
  const search = screen.getByLabelText("Item 1 search inventory");
  await user.clear(search);
  await user.type(search, name);
  // The option reads "Pump PMP · 4 in stock": match the name, then the SKU.
  await user.click(await screen.findByRole("option", { name: new RegExp(`^${name} ?[A-Z]+ ·`) }));
  await user.click(screen.getByRole("button", { name: "Add" }));
}

describe("ItemSetPicker", () => {
  it("adds items as chips, refuses duplicates, and finalises the names into the description", async () => {
    const calls: string[] = [];
    serveCatalogue(calls);
    const user = userEvent.setup();
    renderWithProviders(<Harness initial={[{ ...emptyLine(), description: "" }]} />);

    expect(screen.getByRole("button", { name: "Finalise Description" })).toBeDisabled();
    await addItem(user, "Pump");
    await addItem(user, "Pump Base Frame");
    await addItem(user, "Coupling");
    await addItem(user, "Coupling");
    expect(screen.getByText("Coupling is already in this line.")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem").filter((li) => li.closest('[aria-label="Item 1 items"]'))).toHaveLength(3);
    // An out-of-stock item is flagged, not refused.
    expect(screen.getByText("Out of stock")).toBeInTheDocument();

    // The rate is the items' selling prices x their quantities, added up.
    expect(screen.getByLabelText("Item 1 rate")).toHaveValue("12500");
    fireEvent.change(screen.getByLabelText("Pump Base Frame quantity per unit"), { target: { value: "2" } });
    expect(screen.getByLabelText("Item 1 rate")).toHaveValue("14500");
    expect(screen.getByText("Items total")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Finalise Description" }));
    const box = screen.getByLabelText("Item 1 description");
    expect(box).toHaveValue("Pump, Pump Base Frame, Coupling");

    // Finalised: chips are fixed, the text stays editable.
    expect(screen.queryByRole("button", { name: "Remove Pump" })).toBeNull();
    expect(screen.getByRole("button", { name: "Customize" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Customize" }));
    expect(box).toHaveFocus();
    await user.type(box, " with motor");
    expect(box).toHaveValue("Pump, Pump Base Frame, Coupling with motor");

    // Items are kept by inventory id with their own quantity; the text is not parsed.
    expect(last[0].components.map((c) => [c.product_id, c.quantity])).toEqual([
      [1, "1"],
      [2, "2"],
      [3, "1"],
    ]);
    // Only reads went out (inventory search, settings): no save, nothing that could move stock.
    expect(calls.filter((c) => !c.startsWith("GET "))).toEqual([]);
    expect(calls).toContain("GET /api/products/lookup");
  });

  it("asks before replacing the user's own words on re-finalising", async () => {
    serveCatalogue([]);
    const user = userEvent.setup();
    renderWithProviders(<Harness initial={[{ ...emptyLine(), description: "" }]} />);
    await addItem(user, "Pump");
    await user.click(screen.getByRole("button", { name: "Finalise Description" }));
    const box = screen.getByLabelText("Item 1 description");
    await user.type(box, " set, as per data sheet");

    // Change the items, then finalise again: the edited text is not silently lost.
    await user.click(screen.getByRole("button", { name: "Change items" }));
    await addItem(user, "Coupling");
    await user.click(screen.getByRole("button", { name: "Finalise Description" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Replace it with “Pump, Coupling”?");
    await user.click(screen.getByRole("button", { name: "Keep my text" }));
    expect(box).toHaveValue("Pump set, as per data sheet");

    await user.click(screen.getByRole("button", { name: "Finalise Description" }));
    await user.click(screen.getByRole("button", { name: "Replace" }));
    expect(box).toHaveValue("Pump, Coupling");
  });

  it("keeps a rate the user typed when the items change", async () => {
    serveCatalogue([]);
    const user = userEvent.setup();
    renderWithProviders(<Harness initial={[{ ...emptyLine(), description: "" }]} />);
    await addItem(user, "Pump");
    const rate = screen.getByLabelText("Item 1 rate");
    expect(rate).toHaveValue("10000");
    await user.clear(rate);
    await user.type(rate, "9500");
    await addItem(user, "Coupling");
    expect(rate).toHaveValue("9500");
  });

  it("removing every item leaves an ordinary editable line", async () => {
    serveCatalogue([]);
    const user = userEvent.setup();
    renderWithProviders(<Harness initial={[{ ...emptyLine(), description: "" }]} />);
    await addItem(user, "Pump");
    await user.click(screen.getByRole("button", { name: "Remove Pump" }));
    expect(last[0].components).toEqual([]);
    expect(screen.getByRole("button", { name: "Finalise Description" })).toBeDisabled();
  });

  it("sends each item by inventory id and quantity; the line has no single product", () => {
    const d = emptyDraft();
    d.customer_id = "1";
    d.lines = [
      {
        ...emptyLine(),
        description: "Pump set",
        quantity: "2",
        rate: "50000",
        unit_label: "Set",
        components: [
          { product_id: 1, name: "Pump", quantity: "1" },
          { product_id: 2, name: "Pump Base Frame", quantity: "2" },
        ],
        finalisedText: "Pump, Pump Base Frame",
      },
    ];
    const line = toCreate(d, true).lines[0];
    expect(line.product_id).toBeNull();
    expect(line.description).toBe("Pump set");
    expect(line.components).toEqual([
      { product_id: 1, name: "Pump", quantity: 1 },
      { product_id: 2, name: "Pump Base Frame", quantity: 2 },
    ]);
  });

  it("is read-only in a negotiation", () => {
    const line: DraftLine = {
      ...emptyLine(),
      description: "Pump",
      components: [{ product_id: 1, name: "Pump", quantity: "1" }],
      finalisedText: "Pump",
    };
    renderWithProviders(<LinesEditor lines={[line]} onChange={() => {}} errors={{}} readOnly={false} priceOnly />);
    expect(screen.queryByLabelText("Item 1 search inventory")).toBeNull();
    expect(screen.queryByRole("button", { name: "Remove Pump" })).toBeNull();
    expect(screen.getByLabelText("Pump quantity per unit")).toHaveAttribute("readonly");
  });
});

