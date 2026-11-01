import { describe, expect, it } from "vitest";
import { useState } from "react";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/render";
import { ContactListField } from "./ContactListField";
import { ContactsCell } from "./ContactsCell";
import { CustomerFormDrawer } from "../customers/components/CustomerFormDrawer";
import { SupplierFormDrawer } from "../suppliers/components/SupplierFormDrawer";

function Harness({ initial = [] as string[], showErrors = false }) {
  const [values, setValues] = useState<string[]>(initial);
  return (
    <>
      <ContactListField
        kind="email"
        label="Emails"
        values={values}
        onChange={setValues}
        showErrors={showErrors}
      />
      <output data-testid="values">{JSON.stringify(values)}</output>
    </>
  );
}

describe("ContactListField", () => {
  it("always shows at least one empty row", () => {
    render(<Harness />);
    expect(screen.getByLabelText("Emails 1")).toHaveValue("");
    expect(screen.getByRole("button", { name: "+ Add Email" })).toBeInTheDocument();
  });

  it("adds and removes rows", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["a@x.in"]} />);
    await user.click(screen.getByRole("button", { name: "+ Add Email" }));
    await user.type(screen.getByLabelText("Emails 2"), "b@x.in");
    expect(screen.getByTestId("values")).toHaveTextContent('["a@x.in","b@x.in"]');
    await user.click(screen.getByRole("button", { name: "Remove email 1" }));
    expect(screen.getByTestId("values")).toHaveTextContent('["b@x.in"]');
    expect(screen.queryByLabelText("Emails 2")).not.toBeInTheDocument();
  });

  it("flags an invalid row only when asked to", () => {
    const { rerender } = render(<Harness initial={["nope", "ok@x.in"]} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    rerender(<Harness initial={["nope", "ok@x.in"]} showErrors />);
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.getByLabelText("Emails 1")).toHaveAttribute("aria-invalid", "true");
  });
});

describe("ContactsCell", () => {
  it("shows the first value and a +N chip with the rest in the tooltip", () => {
    render(<ContactsCell values={["a@x.in", "b@x.in", "c@x.in"]} fallback="a@x.in" />);
    expect(screen.getByText("a@x.in")).toBeInTheDocument();
    expect(screen.getByText("+2")).toBeInTheDocument();
    expect(screen.getByTitle(/b@x\.in/)).toBeInTheDocument();
  });
});

/** GST number, city, state and pin code are mandatory on both forms. */
async function fillPlace(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/^gst number/i), "33AAACC1234A1Z5");
  await user.type(screen.getByLabelText(/^city/i), "Salem");
  await user.type(screen.getByLabelText(/^state/i), "Tamil Nadu");
  await user.type(screen.getByLabelText(/^pin code/i), "636016");
}

describe("forms send lists", () => {
  it("customer form sends cleaned emails and phones", async () => {
    const user = userEvent.setup();
    let sent: Record<string, unknown> | null = null;
    server.use(
      http.post("/api/customers", async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: 1 }, { status: 201 });
      }),
    );
    renderWithProviders(<CustomerFormDrawer open customer={null} onClose={() => {}} />);
    await user.type(screen.getByLabelText(/^company name/i), "Multi Co");
    await fillPlace(user);
    await user.type(screen.getByLabelText("Email IDs 1"), " a@x.in ");
    await user.click(screen.getByRole("button", { name: "+ Add Email" }));
    await user.type(screen.getByLabelText("Email IDs 2"), "b@x.in");
    await user.click(screen.getByRole("button", { name: "+ Add Mobile" }));
    await user.type(screen.getByLabelText("Mobile Numbers 2"), "+91 98400 12345");
    await user.click(screen.getByRole("button", { name: /add customer/i }));

    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent).toMatchObject({
      emails: ["a@x.in", "b@x.in"],
      phones: ["+91 98400 12345"],
      email: "a@x.in",
      phone: "+91 98400 12345",
    });
  });

  it("supplier form refuses to submit an invalid phone", async () => {
    const user = userEvent.setup();
    let called = false;
    server.use(
      http.post("/api/suppliers", () => {
        called = true;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    renderWithProviders(<SupplierFormDrawer open supplier={null} onClose={() => {}} />);
    await user.type(screen.getByLabelText(/^supplier name/i), "KSB");
    await fillPlace(user);
    await user.type(screen.getByLabelText("Mobile Numbers 1"), "12ab");
    await user.click(screen.getByRole("button", { name: /add supplier/i }));
    expect(await screen.findByText(/digits, spaces/)).toBeInTheDocument();
    expect(called).toBe(false);
  });
});
