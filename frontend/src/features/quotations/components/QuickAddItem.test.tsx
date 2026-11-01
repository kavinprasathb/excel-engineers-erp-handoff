import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { server } from "../../../test/server";
import { renderWithProviders } from "../../../test/render";
import { ProductPicker } from "./ProductPicker";
import type { ProductLookup } from "../../../api/types";

describe("Adding an item that is not in inventory", () => {
  it("offers to add it, saves it as a to-order item and hands it to the quote", async () => {
    let sent: Record<string, unknown> | null = null;
    server.use(
      http.get("/api/products/lookup", () => HttpResponse.json([])),
      http.get("/api/suppliers/options", () => HttpResponse.json([{ id: 7, name: "KSB" }])),
      http.post("/api/products", async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            id: 41,
            sku: "ORD-0001",
            name: sent.name,
            model_number: "",
            description: "",
            unit: "Each",
            hsn_code: "",
            purchase_cost: 0,
            sell_price: 0,
            gst_rate_bp: 1800,
            is_active: true,
            stock_type: "to_order",
            supplier: null,
            category: null,
            inventory: { quantity_on_hand: 0, quantity_reserved: 0, quantity_available: 0 },
          },
          { status: 201 },
        );
      }),
    );
    const picked: ProductLookup[] = [];
    const user = userEvent.setup();
    renderWithProviders(<ProductPicker onPick={(p) => picked.push(p)} />);

    await user.type(screen.getByLabelText("Add from catalogue"), "ETN 125-100-250 GG");
    await user.click(await screen.findByRole("button", { name: /Add “ETN 125-100-250 GG” as a new item/ }));
    expect(screen.getByLabelText("New item name")).toHaveValue("ETN 125-100-250 GG");
    expect(screen.getByLabelText("New item type")).toHaveValue("to_order");
    await user.click(screen.getByRole("button", { name: "Save & add" }));

    await screen.findByLabelText("Add from catalogue");
    expect(sent).toMatchObject({ name: "ETN 125-100-250 GG", stock_type: "to_order", opening_quantity: 0, sku: "" });
    expect(picked).toHaveLength(1);
    expect(picked[0]).toMatchObject({ id: 41, sku: "ORD-0001", stock_type: "to_order" });
  });
});
