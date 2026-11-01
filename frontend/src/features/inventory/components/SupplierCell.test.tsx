import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { server } from "../../../test/server";
import { renderWithProviders } from "../../../test/render";
import { useInventory } from "../api";
import { SupplierCell } from "./SupplierCell";
import type { InventoryRow, Page } from "../../../api/types";

const UNTAGGED: InventoryRow = {
  product_id: 12,
  sku: "KSB-ETA-65-200",
  name: "KSB Etanorm 65-200",
  model_number: "65-200",
  unit: "piece",
  supplier: null,
  category: { id: 1, name: "Centrifugal Pumps" },
  quantity_on_hand: 12,
  quantity_reserved: 3,
  quantity_available: 9,
  is_low_stock: false,
  is_out_of_stock: false,
};

function page(row: InventoryRow): Page<InventoryRow> {
  return { items: [row], total: 1, page: 1, page_size: 25, pages: 1 };
}

/**
 * The cell is driven from the query cache, not from props held in the test —
 * which is the behaviour under test: the mutation writes the refreshed row
 * back with setQueryData and the cell re-renders from it.
 */
function Harness() {
  const inventory = useInventory({});
  const row = inventory.data?.items[0];
  if (!row) return <p>Loading…</p>;
  return <SupplierCell row={row} />;
}

describe("SupplierCell", () => {
  it("flags an untagged product instead of showing a blank cell", async () => {
    server.use(http.get("/api/inventory", () => HttpResponse.json(page(UNTAGGED))));

    renderWithProviders(<Harness />);

    expect(await screen.findByRole("button", { name: /set supplier/i })).toBeInTheDocument();
  });

  it("sets the supplier and shows the new name from the server's row", async () => {
    const user = userEvent.setup();
    let sent: unknown = null;

    server.use(
      http.get("/api/inventory", () => HttpResponse.json(page(UNTAGGED))),
      http.get("/api/suppliers/options", () =>
        HttpResponse.json([
          { id: 3, name: "KSB Pumps Ltd" },
          { id: 4, name: "CRI Pumps" },
        ]),
      ),
      http.patch("/api/inventory/12/supplier", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ ...UNTAGGED, supplier: { id: 4, name: "CRI Pumps" } });
      }),
    );

    renderWithProviders(<Harness />);

    await user.click(await screen.findByRole("button", { name: /set supplier/i }));
    const select = await screen.findByLabelText(/supplier for ksb etanorm/i);
    await waitFor(() => expect(screen.getByRole("option", { name: "CRI Pumps" })).toBeEnabled());
    await user.selectOptions(select, "4");

    await waitFor(() => expect(sent).toEqual({ supplier_id: 4 }));
    expect(await screen.findByText("CRI Pumps")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /set supplier/i })).not.toBeInTheDocument();
  });

  it("keeps the flag and explains the refusal when the server rejects the change", async () => {
    const user = userEvent.setup();

    server.use(
      http.get("/api/inventory", () => HttpResponse.json(page(UNTAGGED))),
      http.get("/api/suppliers/options", () =>
        HttpResponse.json([{ id: 4, name: "CRI Pumps" }]),
      ),
      http.patch("/api/inventory/12/supplier", () =>
        HttpResponse.json(
          { error: { code: "not_found", message: "That supplier no longer exists." } },
          { status: 404 },
        ),
      ),
    );

    renderWithProviders(<Harness />);

    await user.click(await screen.findByRole("button", { name: /set supplier/i }));
    const select = await screen.findByLabelText(/supplier for ksb etanorm/i);
    await waitFor(() => expect(screen.getByRole("option", { name: "CRI Pumps" })).toBeEnabled());
    await user.selectOptions(select, "4");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "That supplier no longer exists.",
    );
  });
});
