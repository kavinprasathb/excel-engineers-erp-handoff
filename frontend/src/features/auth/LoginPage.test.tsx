import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/render";
import LoginPage from "./LoginPage";

const NOT_AUTHENTICATED = http.get("/api/auth/me", () =>
  HttpResponse.json(
    { error: { code: "not_authenticated", message: "Sign in to continue." } },
    { status: 401 },
  ),
);

describe("LoginPage", () => {
  it("validates before it hits the network", async () => {
    const user = userEvent.setup();
    server.use(NOT_AUTHENTICATED);
    renderWithProviders(<LoginPage />);

    await user.click(await screen.findByRole("button", { name: /login/i }));

    expect(await screen.findByText("Enter your email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
  });

  it("posts the credentials and seeds the session on success", async () => {
    const user = userEvent.setup();
    let body: unknown = null;
    server.use(
      NOT_AUTHENTICATED,
      http.post("/api/auth/login", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({
          user: { id: 1, email: "admin@excelengineers.in", full_name: "Admin", role: "admin" },
        });
      }),
    );

    const { client } = renderWithProviders(<LoginPage />);

    await user.type(await screen.findByLabelText(/email/i), "admin@excelengineers.in");
    await user.type(screen.getByLabelText(/password/i), "correct horse");
    await user.click(screen.getByRole("button", { name: /login/i }));

    await waitFor(() => {
      expect(body).toEqual({ email: "admin@excelengineers.in", password: "correct horse" });
    });
    await waitFor(() => {
      expect(client.getQueryData(["me"])).toMatchObject({ email: "admin@excelengineers.in" });
    });
  });

  it("shows a human message for invalid credentials, not the raw code", async () => {
    const user = userEvent.setup();
    server.use(
      NOT_AUTHENTICATED,
      http.post("/api/auth/login", () =>
        HttpResponse.json(
          { error: { code: "invalid_credentials", message: "Invalid credentials." } },
          { status: 401 },
        ),
      ),
    );

    renderWithProviders(<LoginPage />);

    await user.type(await screen.findByLabelText(/email/i), "admin@excelengineers.in");
    await user.type(screen.getByLabelText(/password/i), "wrong");
    await user.click(screen.getByRole("button", { name: /login/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("That email and password do not match an account.");
    // The form must stay filled in — retyping the email after a typo in the
    // password is the fastest way to make someone hate a login screen.
    expect(screen.getByLabelText(/email/i)).toHaveValue("admin@excelengineers.in");
  });
});
