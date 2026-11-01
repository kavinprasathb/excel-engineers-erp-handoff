import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { AvailabilityCell } from "./AvailabilityCell";
import type { InventoryRow } from "../../../api/types";

function row(overrides: Partial<InventoryRow>): InventoryRow {
  return {
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
    ...overrides,
  };
}

describe("AvailabilityCell", () => {
  it("is quiet when the server says the level is fine", () => {
    render(<AvailabilityCell row={row({})} />);

    expect(screen.getByText("9")).toHaveClass("text-ink");
    expect(screen.queryByText("Low")).not.toBeInTheDocument();
    expect(screen.queryByText("Out of stock")).not.toBeInTheDocument();
  });

  it("goes amber when is_low_stock is set", () => {
    render(<AvailabilityCell row={row({ quantity_available: 2, is_low_stock: true })} />);

    expect(screen.getByText("2")).toHaveClass("text-amber");
    expect(screen.getByText("Low")).toBeInTheDocument();
  });

  it("goes red when is_out_of_stock is set, and out beats low", () => {
    render(
      <AvailabilityCell
        row={row({ quantity_available: 0, is_low_stock: true, is_out_of_stock: true })}
      />,
    );

    expect(screen.getByText("0")).toHaveClass("text-red");
    expect(screen.getByText("Out of stock")).toBeInTheDocument();
    expect(screen.queryByText("Low")).not.toBeInTheDocument();
  });

  it("renders the server's available figure rather than on_hand - reserved", () => {
    // A deliberately inconsistent row: if the cell ever does the subtraction
    // itself it prints 9 here, and this test is the thing that catches it.
    render(
      <AvailabilityCell
        row={row({ quantity_on_hand: 12, quantity_reserved: 3, quantity_available: 4 })}
      />,
    );

    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.queryByText("9")).not.toBeInTheDocument();
  });
});
