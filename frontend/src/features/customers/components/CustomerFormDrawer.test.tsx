import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { UserEvent } from "@testing-library/user-event";
import { server } from "../../../test/server";
import { renderWithProviders } from "../../../test/render";
import { CustomerFormDrawer } from "./CustomerFormDrawer";
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
  gstin: "33AAACC1234A1Z5",
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

/** The branches section reads the customer back; answer with the fixture. */
function serveCustomer(customer: Customer) {
  server.use(http.get(`/api/customers/${customer.id}`, () => HttpResponse.json(customer)));
}

async function fillMandatory(user: UserEvent) {
  await user.type(screen.getByLabelText(/^company name/i), "  Chemplast Sanmar Limited  ");
  await user.type(screen.getByLabelText(/^gst number/i), "33aaacc1234a1z5");
  await user.type(screen.getByLabelText(/^city/i), "Mettur Dam");
  await user.type(screen.getByLabelText(/^state/i), "Tamil Nadu");
  await user.type(screen.getByLabelText(/^pin code/i), "636403");
}

describe("CustomerFormDrawer", () => {
  it("refuses to submit without the mandatory fields", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CustomerFormDrawer open customer={null} onClose={() => {}} />);

    await user.click(screen.getByRole("button", { name: /add customer/i }));

    expect(await screen.findByText("Enter a customer name.")).toBeInTheDocument();
    expect(screen.getByText("Enter the GST number.")).toBeInTheDocument();
    expect(screen.getByText("Enter the city.")).toBeInTheDocument();
    expect(screen.getByText("Enter the state.")).toBeInTheDocument();
    expect(screen.getByText("Enter the pin code.")).toBeInTheDocument();
  });

  it("checks the GST number and pin code formats", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CustomerFormDrawer open customer={null} onClose={() => {}} />);

    await user.type(screen.getByLabelText(/^gst number/i), "33ABC");
    await user.type(screen.getByLabelText(/^pin code/i), "6364");
    await user.click(screen.getByRole("button", { name: /add customer/i }));

    expect(await screen.findByText(/valid 15-character GST number/)).toBeInTheDocument();
    expect(screen.getByText("A pin code is 6 digits.")).toBeInTheDocument();
  });

  it("sends blank shipping fields rather than copying billing into them", async () => {
    const user = userEvent.setup();
    let sent: Record<string, unknown> | null = null;
    server.use(
      http.post("/api/customers", async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...CUSTOMER, id: 9 }, { status: 201 });
      }),
    );

    renderWithProviders(<CustomerFormDrawer open customer={null} onClose={() => {}} />);

    await fillMandatory(user);
    await user.click(screen.getByRole("button", { name: /add customer/i }));

    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent).toMatchObject({
      name: "Chemplast Sanmar Limited",
      gstin: "33AAACC1234A1Z5",
      billing_city: "Mettur Dam",
      billing_state: "Tamil Nadu",
      billing_pincode: "636403",
      shipping_city: "",
      shipping_address_line1: "",
      shipping_pincode: "",
    });
    // The code is the server's: never sent.
    expect(sent).not.toHaveProperty("code");
  });

  it("patches the existing customer when editing, and shows its read-only code", async () => {
    const user = userEvent.setup();
    let path = "";
    let sent: Record<string, unknown> | null = null;
    serveCustomer(CUSTOMER);
    server.use(
      http.patch("/api/customers/7", async ({ request }) => {
        path = new URL(request.url).pathname;
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...CUSTOMER, name: "Chemplast Sanmar Ltd" });
      }),
    );

    renderWithProviders(<CustomerFormDrawer open customer={CUSTOMER} onClose={() => {}} />);

    expect(screen.getByLabelText(/^company name/i)).toHaveValue("Chemplast Sanmar Limited");
    expect(screen.getByLabelText(/^customer code/i)).toHaveValue("CUST-0007");
    expect(screen.getByLabelText(/^customer code/i)).toHaveAttribute("readonly");
    await user.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(path).toBe("/api/customers/7"));
    expect(sent).not.toHaveProperty("code");
    expect(sent).not.toHaveProperty("branches");
    expect(sent).not.toHaveProperty("missing_fields");
  });

  it("hides shipping state and pincode; shows notes under shipping", () => {
    renderWithProviders(<CustomerFormDrawer open customer={null} onClose={() => {}} />);

    expect(screen.queryByLabelText(/shipping state/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/shipping pincode/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/shipping city/i)).toBeInTheDocument();
    expect(screen.getAllByLabelText(/^notes/i)).toHaveLength(1);
  });

  it("keeps hidden address values when editing an existing customer", async () => {
    const user = userEvent.setup();
    const stored: Customer = {
      ...CUSTOMER,
      shipping_address_line1: "Plant 2",
      shipping_state: "Karnataka",
      shipping_pincode: "560001",
    };
    let sent: Record<string, unknown> | null = null;
    serveCustomer(stored);
    server.use(
      http.patch("/api/customers/7", async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(stored);
      }),
    );

    renderWithProviders(<CustomerFormDrawer open customer={stored} onClose={() => {}} />);

    const city = screen.getByLabelText(/^city/i);
    await user.clear(city);
    await user.type(city, "Salem");
    await user.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent).toMatchObject({
      billing_city: "Salem",
      billing_state: "Tamil Nadu",
      billing_pincode: "636403",
      shipping_state: "Karnataka",
      shipping_pincode: "560001",
    });
  });

  it("flags an older record's missing details for completion", async () => {
    const legacy: Customer = {
      ...CUSTOMER,
      gstin: "",
      billing_pincode: "",
      missing_fields: ["GST Number", "Pin Code"],
    };
    serveCustomer(legacy);
    renderWithProviders(<CustomerFormDrawer open customer={legacy} onClose={() => {}} />);

    expect(screen.getByRole("status")).toHaveTextContent("Please complete: GST Number, Pin Code.");
  });

  it("lists branches and offers Add Branch when editing", async () => {
    const user = userEvent.setup();
    serveCustomer({
      ...CUSTOMER,
      branches: [
        {
          id: 3,
          code: "CUST-0007-BR01",
          name: "Mettur Plant",
          gstin: "33AAACC1234A2Z4",
          contact_person: "",
          designation: "",
          emails: [],
          phones: [],
          address_line1: "",
          city: "Mettur Dam",
          state: "Tamil Nadu",
          pincode: "636403",
          is_active: true,
        },
      ],
    });
    renderWithProviders(<CustomerFormDrawer open customer={CUSTOMER} onClose={() => {}} />);

    expect(await screen.findByText("Mettur Plant")).toBeInTheDocument();
    expect(screen.getByText(/CUST-0007-BR01/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /add branch/i }));
    expect(screen.getByLabelText(/^branch name/i)).toBeInTheDocument();
  });

  it("renders the server's reason in place when the name collides", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("/api/customers", () =>
        HttpResponse.json(
          {
            error: {
              code: "duplicate",
              message: "A customer named Chemplast Sanmar Limited already exists.",
            },
          },
          { status: 409 },
        ),
      ),
    );

    renderWithProviders(<CustomerFormDrawer open customer={null} onClose={() => {}} />);

    await fillMandatory(user);
    await user.click(screen.getByRole("button", { name: /add customer/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "A customer named Chemplast Sanmar Limited already exists.",
    );
  });
});
