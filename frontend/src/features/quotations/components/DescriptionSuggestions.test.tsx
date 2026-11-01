import { useState } from "react";
import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { server } from "../../../test/server";
import { renderWithProviders } from "../../../test/render";
import { LinesEditor } from "./LinesEditor";
import { emptyLine } from "../draft";
import type { DraftLine } from "../draft";
import type { ItemSuggestion } from "../../../api/types";

const SEAL: ItemSuggestion = {
  description: "Mechanical seal K6BM ETN",
  details: "Model: ETN 65-50-160 GG",
  part_no: "433",
  moc: "Std",
  unit: "No",
  rate_paise: 1450000,
  hsn_code: "84139120",
  offer_no: "ESQSP-25-160",
  offer_date: "2025-04-03",
  customer_name: "Hindustan Unilever Ltd",
  same_customer: true,
  source: "past offer",
};

let last: DraftLine[] = [];
function Harness() {
  const [lines, setLines] = useState<DraftLine[]>([{ ...emptyLine(), description: "" }]);
  return (
    <LinesEditor
      lines={lines}
      onChange={(next) => {
        last = next;
        setLines(next);
      }}
      errors={{}}
      readOnly={false}
      layout="spares"
      printColumns={["moc", "part_no", "unit"]}
      customerId={7}
    />
  );
}

describe("Description suggestions", () => {
  it("shows what was quoted before, with customer and date, and fills the line on click", async () => {
    let asked = "";
    server.use(
      http.get("/api/quotations/item-suggestions", ({ request }) => {
        asked = new URL(request.url).search;
        return HttpResponse.json([SEAL]);
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<Harness />);
    await user.type(screen.getByLabelText("Item 1 description"), "seal etn");

    const option = await screen.findByRole("option", { name: /Mechanical seal K6BM ETN/ });
    expect(option).toHaveTextContent("Hindustan Unilever Ltd");
    expect(option).toHaveTextContent("03.04.2025");
    expect(option).toHaveTextContent("This customer");
    expect(option).toHaveTextContent("₹14,500");
    expect(asked).toContain("customer_id=7");

    await user.click(option);
    expect(last[0]).toMatchObject({
      description: "Mechanical seal K6BM ETN",
      rate: "14500",
      hsn_code: "84139120",
      moc: "Std",
      part_no: "433",
      unit_label: "No",
    });
    expect(screen.queryByRole("listbox", { name: /earlier quotes/ })).toBeNull();
  });

  it("asks nothing for fewer than three letters", async () => {
    let calls = 0;
    server.use(
      http.get("/api/quotations/item-suggestions", () => {
        calls += 1;
        return HttpResponse.json([SEAL]);
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<Harness />);
    await user.type(screen.getByLabelText("Item 1 description"), "se");
    await new Promise((r) => setTimeout(r, 400));
    expect(calls).toBe(0);
  });
});
