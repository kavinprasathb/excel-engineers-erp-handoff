import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { server } from "../../../test/server";
import { renderWithProviders } from "../../../test/render";
import { AdjustStockModal } from "./AdjustStockModal";
import type { InventoryRow } from "../../../api/types";

const ROW: InventoryRow = {
  product_id: 12,
  sku: "KSB-ETA-65-200",
  name: "KSB Etanorm 65-200",
  model_number: "65-200",
  unit: "piece",
  supplier: { id: 3, name: "KSB Pumps Ltd" },
  category: { id: 1, name: "Centrifugal Pumps" },
  quantity_on_hand: 12,
  quantity_reserved: 3,
  quantity_available: 9,
  is_low_stock: false,
  is_out_of_stock: false,
};

describe("AdjustStockModal", () => {
  it("composes a positive delta when adding", async () => {
    const user = userEvent.setup();
    let sent: unknown = null;
    server.use(
      http.post("/api/inventory/12/adjust", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ ...ROW, quantity_on_hand: 17, quantity_available: 14 });
      }),
    );

    renderWithProviders(<AdjustStockModal row={ROW} onClose={() => {}} />);

    await user.type(screen.getByLabelText(/quantity/i), "5");
    await user.type(screen.getByLabelText(/note/i), "restocked");
    await user.click(screen.getByRole("button", { name: /save adjustment/i }));

    await waitFor(() => expect(sent).toEqual({ delta: 5, note: "restocked" }));
  });

  it("negates the quantity when removing, without the user typing a minus sign", async () => {
    const user = userEvent.setup();
    let sent: unknown = null;
    server.use(
      http.post("/api/inventory/12/adjust", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({
          ...ROW,
          quantity_on_hand: 10,
          quantity_available: 7,
        });
      }),
    );

    renderWithProviders(<AdjustStockModal row={ROW} onClose={() => {}} />);

    await user.click(screen.getByRole("radio", { name: /remove stock/i }));
    await user.type(screen.getByLabelText(/quantity/i), "2");
    await user.click(screen.getByRole("button", { name: /save adjustment/i }));

    await waitFor(() => expect(sent).toEqual({ delta: -2, note: "" }));

    // The resulting stock is shown, so the user does not have to go back to
    // the list to find out what the count is now.
    expect(await screen.findByText("Stock updated.")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("refuses to send a zero or fractional quantity", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdjustStockModal row={ROW} onClose={() => {}} />);

    await user.type(screen.getByLabelText(/quantity/i), "0");
    await user.click(screen.getByRole("button", { name: /save adjustment/i }));

    expect(
      await screen.findByText("Enter a whole quantity greater than zero."),
    ).toBeInTheDocument();
  });

  it("shows the server's reason when the stock is reserved", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("/api/inventory/12/adjust", () =>
        HttpResponse.json(
          {
            error: {
              code: "insufficient_stock",
              message: "Only 3 in stock; cannot remove 5.",
              details: { in_stock: 3, requested: 5 },
            },
          },
          { status: 409 },
        ),
      ),
    );

    renderWithProviders(<AdjustStockModal row={ROW} onClose={() => {}} />);

    await user.click(screen.getByRole("radio", { name: /remove stock/i }));
    await user.type(screen.getByLabelText(/quantity/i), "5");
    await user.click(screen.getByRole("button", { name: /save adjustment/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Only 3 in stock; cannot remove 5.",
    );
  });
});
