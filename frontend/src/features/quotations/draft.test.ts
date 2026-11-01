import { describe, expect, it } from "vitest";
import {
  draftTotalPaise,
  emptyDraft,
  emptyLine,
  paiseFromRupees,
  rupeesFromPaise,
  toCreate,
  validate,
} from "./draft";

describe("quotation draft", () => {
  it("keeps whole rupees whole and shows paise only when present", () => {
    expect(rupeesFromPaise(1476000)).toBe("14760");
    expect(rupeesFromPaise(1476050)).toBe("14760.50");
    expect(paiseFromRupees("14,760")).toBe(1476000);
    expect(paiseFromRupees("0.1")).toBe(10);
  });

  it("totals lines from the strings the user typed", () => {
    const d = emptyDraft();
    d.lines = [
      { ...emptyLine(), description: "A", quantity: "2", rate: "100" },
      { ...emptyLine(), description: "B", quantity: "1", rate: "250.5" },
    ];
    expect(draftTotalPaise(d)).toBe(45050);
  });

  it("refuses to save without a customer or an item, and names the bad line", () => {
    const d = emptyDraft();
    const e1 = validate(d);
    expect(e1.customer_id).toBeTruthy();
    expect(e1.lines).toBeTruthy();

    d.customer_id = "3";
    d.lines = [{ ...emptyLine(), description: "", quantity: "1", rate: "5" }];
    const e2 = validate(d);
    expect(e2.line?.[d.lines[0].key]).toMatch(/describe/i);

    d.lines[0].description = "Gasket";
    d.lines[0].quantity = "0";
    expect(validate(d).line?.[d.lines[0].key]).toMatch(/quantity/i);

    d.lines[0].quantity = "1";
    expect(validate(d)).toEqual({});
  });

  it("allows any rate — there is no floor, and zero is a valid price", () => {
    const d = emptyDraft();
    d.customer_id = "1";
    d.lines = [{ ...emptyLine(), product_id: 9, description: "Pump", quantity: "1", rate: "0" }];
    expect(validate(d)).toEqual({});
    expect(toCreate(d, true).lines[0]).toEqual({
      kind: "product",
      unit_label: "Each",
      hsn_code: "",
      product_id: 9,
      description: "Pump",
      quantity: 1,
      rate_paise: 0,
      deviations: [],
      components: [],
      // Technical sheet fields; empty on a standard quotation.
      service: "",
      tech_values: [],
      // Spares / pump offer fields; empty on a plain line.
      part_no: "",
      moc: "",
      delivery: "",
      supply_scope: "",
    });
  });

  it("omits terms on create when the defaults should be used", () => {
    const d = emptyDraft();
    d.customer_id = "1";
    expect(toCreate(d, true)).not.toHaveProperty("terms");
    d.terms = [{ key: "k", label: "Delivery", text: "3 weeks", included: false }];
    expect(toCreate(d, false).terms).toEqual([
      { label: "Delivery", text: "3 weeks", included: false },
    ]);
  });
});

describe("version labels", () => {
  it("names the original, revisions, negotiations and both", async () => {
    const { stageLabel, stageOf } = await import("./format");
    expect(stageLabel({ rev_no: 0, neg_no: 0 })).toBe("Initial quote");
    expect(stageLabel({ rev_no: 2, neg_no: 0 })).toBe("Revision R2");
    expect(stageLabel({ rev_no: 0, neg_no: 3 })).toBe("Negotiation N3");
    expect(stageLabel({ rev_no: 2, neg_no: 1 })).toBe("Revision R2 · Negotiation N1");
    expect([stageOf({ rev_no: 0, neg_no: 0 }), stageOf({ rev_no: 1, neg_no: 0 }), stageOf({ rev_no: 1, neg_no: 1 })]).toEqual([
      "quotation",
      "revised",
      "negotiation",
    ]);
  });
});
