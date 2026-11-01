import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/render";
import { LetterheadCard } from "./LetterheadCard";
import type { Settings } from "../../api/types";

const SETTINGS: Settings = {
  company_name: "Excel Engineers",
  low_stock_threshold: 5,
  default_gst_rate_bp: 1800,
  company_address_line1: "G2, VKP Residency, 146, Dhayanandhar Street",
  company_address_line2: "New Fairlands",
  company_city: "Salem",
  company_state: "Tamil Nadu",
  company_pincode: "636016",
  company_gstin: "33AAIFE2328P1Z9",
  company_phone: "0427 244 0808",
  company_mobile: "94449 15716",
  company_email: "excelengrs@gmail.com",
  signatory_name: "M. Rajamuthaiyah",
  signatory_designation: "",
  quotation_terms_defaults: { pumps: [], valves: [], spares: [] },
  quotation_spec_defaults: [],
};

function stubSettings() {
  server.use(http.get("/api/settings", () => HttpResponse.json(SETTINGS)));
}

describe("LetterheadCard", () => {
  it("seeds every field from the server and saves only the letterhead", async () => {
    const user = userEvent.setup();
    stubSettings();
    let sent: Record<string, unknown> | null = null;
    server.use(
      http.patch("/api/settings", async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...SETTINGS, ...sent });
      }),
    );

    renderWithProviders(<LetterheadCard />);

    const city = await screen.findByLabelText(/^city$/i);
    expect(city).toHaveValue("Salem");
    await user.clear(city);
    await user.type(city, "Chennai");
    await user.click(screen.getByRole("button", { name: /save letterhead/i }));

    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent).toMatchObject({ company_city: "Chennai", company_gstin: "33AAIFE2328P1Z9" });
    // The card owns the letterhead and nothing else: it must never send the
    // company name or the stock threshold, which belong to CompanyCard.
    expect(sent).not.toHaveProperty("company_name");
    expect(sent).not.toHaveProperty("low_stock_threshold");
  });

  it("refuses a GSTIN that is not fifteen characters, before any request", async () => {
    const user = userEvent.setup();
    stubSettings();
    let patched = false;
    server.use(
      http.patch("/api/settings", () => {
        patched = true;
        return HttpResponse.json(SETTINGS);
      }),
    );

    renderWithProviders(<LetterheadCard />);

    const gstin = await screen.findByLabelText(/gstin/i);
    await user.clear(gstin);
    await user.type(gstin, "33AAIFE");
    await user.click(screen.getByRole("button", { name: /save letterhead/i }));

    expect(await screen.findByText(/A GSTIN is 15 letters and digits/)).toBeInTheDocument();
    expect(patched).toBe(false);
  });

  it("lets a line be blanked — blank means do not print it", async () => {
    const user = userEvent.setup();
    stubSettings();
    let sent: Record<string, unknown> | null = null;
    server.use(
      http.patch("/api/settings", async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...SETTINGS, ...sent });
      }),
    );

    renderWithProviders(<LetterheadCard />);

    await user.clear(await screen.findByLabelText(/address line 2/i));
    await user.click(screen.getByRole("button", { name: /save letterhead/i }));

    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent).toMatchObject({ company_address_line2: "" });
  });
});
