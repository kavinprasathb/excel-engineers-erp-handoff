import { describe, expect, it } from "vitest";
import { periodRange } from "./period";

describe("periodRange", () => {
  // 26 Sep 2026
  const today = new Date(2026, 8, 26);

  it("resolves whole months", () => {
    expect(periodRange("this-month", today)).toEqual({ from: "2026-09-01", to: "2026-09-30" });
    expect(periodRange("last-month", today)).toEqual({ from: "2026-08-01", to: "2026-08-31" });
    expect(periodRange("last-3-months", today)).toEqual({ from: "2026-07-01", to: "2026-09-30" });
    expect(periodRange("last-6-months", today)).toEqual({ from: "2026-04-01", to: "2026-09-30" });
  });

  it("resolves years, and crosses a year boundary in January", () => {
    expect(periodRange("this-year", today)).toEqual({ from: "2026-01-01", to: "2026-12-31" });
    expect(periodRange("last-year", today)).toEqual({ from: "2025-01-01", to: "2025-12-31" });
    const jan = new Date(2027, 0, 10);
    expect(periodRange("last-month", jan)).toEqual({ from: "2026-12-01", to: "2026-12-31" });
    expect(periodRange("last-3-months", jan)).toEqual({ from: "2026-11-01", to: "2027-01-31" });
  });

  it("leaves all-time and custom open", () => {
    expect(periodRange("all", today)).toEqual({ from: "", to: "" });
    expect(periodRange("custom", today)).toEqual({ from: "", to: "" });
  });
});
