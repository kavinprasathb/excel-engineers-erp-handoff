import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/render";
import { ImportDialog } from "./ImportDialog";
import type { ImportJob } from "../../api/types";

function job(overrides: Partial<ImportJob>): ImportJob {
  return {
    id: "job-1",
    status: "pending",
    filename: "stock.xlsx",
    total_rows: 0,
    processed_rows: 0,
    created_count: 0,
    updated_count: 0,
    skipped_count: 0,
    error_count: 0,
    errors: [],
    column_mapping: {},
    unmapped_headers: [],
    header_row_index: 0,
    message: "",
    created_at: "2026-08-30T09:00:00Z",
    started_at: null,
    finished_at: null,
    ...overrides,
  };
}

/** Serves each poll from a script, and counts how many polls actually happen. */
function pollScript(steps: ImportJob[]) {
  const state = { polls: 0 };
  server.use(
    http.post("/api/imports/products", () => HttpResponse.json(job({}), { status: 202 })),
    http.get("/api/imports/job-1", () => {
      const step = steps[Math.min(state.polls, steps.length - 1)];
      state.polls += 1;
      return HttpResponse.json(step);
    }),
  );
  return state;
}

async function startImport() {
  const user = userEvent.setup();
  renderWithProviders(<ImportDialog open onClose={() => {}} />);

  const file = new File(["sku,name"], "stock.xlsx", { type: "text/csv" });
  await user.upload(screen.getByLabelText(/spreadsheet/i), file);
  await user.click(screen.getByRole("button", { name: /start import/i }));
  return user;
}

describe("ImportDialog", () => {
  it("is indeterminate until the row count is known, then determinate", async () => {
    pollScript([
      job({ status: "running", total_rows: 0 }),
      job({ status: "running", total_rows: 100, processed_rows: 50 }),
      job({ status: "running", total_rows: 100, processed_rows: 50 }),
    ]);

    await startImport();

    // total_rows is still 0: no percentage to report.
    const counting = await screen.findByRole("progressbar");
    expect(counting).not.toHaveAttribute("aria-valuenow");
    expect(screen.getByText("Reading the file…")).toBeInTheDocument();

    await waitFor(
      () => expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50"),
      { timeout: 4000 },
    );
  });

  it("stops polling once the job reaches a terminal status", async () => {
    const state = pollScript([
      job({ status: "running", total_rows: 10, processed_rows: 4 }),
      job({
        status: "completed",
        total_rows: 10,
        processed_rows: 10,
        created_count: 6,
        updated_count: 3,
        skipped_count: 1,
        finished_at: "2026-08-30T09:05:00Z",
      }),
    ]);

    await startImport();

    await screen.findByText("Completed", {}, { timeout: 4000 });
    const pollsAtCompletion = state.polls;

    // Two intervals' worth of real time. If the refetchInterval predicate ever
    // stops returning false on a terminal status, this is where it shows up.
    await new Promise((resolve) => setTimeout(resolve, 2200));
    expect(state.polls).toBe(pollsAtCompletion);
  });

  it("reports the counts, the failed rows and the columns it could not map", async () => {
    pollScript([
      job({
        status: "completed",
        total_rows: 10,
        processed_rows: 10,
        created_count: 6,
        updated_count: 3,
        skipped_count: 1,
        error_count: 205,
        errors: [{ row: 88, column: "quantity", message: "not a number", value: "n/a" }],
        unmapped_headers: ["Godown", "Rate incl. tax"],
        finished_at: "2026-08-30T09:05:00Z",
      }),
    ]);

    await startImport();

    expect(await screen.findByText("Completed", {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.getByText("Created").nextSibling).toHaveTextContent("6");
    expect(screen.getByText("Updated").nextSibling).toHaveTextContent("3");
    expect(screen.getByText("Skipped").nextSibling).toHaveTextContent("1");

    // The list that makes supporting a real Tally export a small change.
    expect(screen.getByText("Unmapped columns")).toBeInTheDocument();
    expect(screen.getByText("Godown")).toBeInTheDocument();
    expect(screen.getByText("Rate incl. tax")).toBeInTheDocument();

    // Truncation is announced rather than silently dropping 204 errors.
    expect(screen.getByText("Showing the first 1 of 205 errors.")).toBeInTheDocument();
    expect(screen.getAllByText("not a number").length).toBeGreaterThan(0);
  });
});
