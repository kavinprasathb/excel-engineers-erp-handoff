import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { server } from "../../../test/server";
import { renderWithProviders } from "../../../test/render";
import { DeleteCustomerDialog } from "./DeleteCustomerDialog";
import type { Customer } from "../../../api/types";

const CUSTOMER: Customer = {
  id: 7,
  code: "CUST-0007",
  name: "Chemplast Sanmar Limited",
  contact_person: "Mr. B. Prathap",
  designation: "Purchase",
  phone: "",
  email: "",
  emails: [],
  phones: [],
  gstin: "",
  billing_address_line1: "Chloro Chemical Division",
  billing_address_line2: "",
  billing_city: "Mettur Dam",
  billing_state: "Tamil Nadu",
  billing_pincode: "636403",
  shipping_address_line1: "",
  shipping_address_line2: "",
  shipping_city: "",
  shipping_state: "",
  shipping_pincode: "",
  notes: "",
  is_active: true,
  branches: [],
  missing_fields: [],
};

describe("DeleteCustomerDialog", () => {
  it("deactivates and reports back", async () => {
    const user = userEvent.setup();
    let called = false;
    server.use(
      http.delete("/api/customers/7", () => {
        called = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    renderWithProviders(<DeleteCustomerDialog customer={CUSTOMER} onClose={() => {}} />);

    expect(screen.getByText(/marked inactive/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^deactivate$/i }));

    await waitFor(() => expect(called).toBe(true));
    expect(await screen.findByText("Chemplast Sanmar Limited deactivated.")).toBeInTheDocument();
  });

  it("renders the 409 in place and withdraws the button, because retrying cannot help", async () => {
    const user = userEvent.setup();
    server.use(
      http.delete("/api/customers/7", () =>
        HttpResponse.json(
          {
            error: {
              code: "conflict",
              message: "3 orders still reference this customer.",
              details: { order_count: 3 },
            },
          },
          { status: 409 },
        ),
      ),
    );

    renderWithProviders(<DeleteCustomerDialog customer={CUSTOMER} onClose={() => {}} />);

    await user.click(screen.getByRole("button", { name: /^deactivate$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "3 orders still reference this customer.",
    );
    expect(screen.queryByRole("button", { name: /^deactivate$/i })).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^close$/i }).length).toBeGreaterThan(0);
  });
});
