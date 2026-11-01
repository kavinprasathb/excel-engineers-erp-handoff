import { Button } from "../../../components/ui/Button";
import { Input } from "../../../components/ui/Input";
import { Textarea } from "../../../components/ui/Textarea";
import { Chip } from "../../../components/ui/Chip";
import { Icon } from "../../../components/ui/Icon";
import { fieldErrorCls } from "../../../components/ui/styles";
import { ProductPicker } from "./ProductPicker";
import { SpecsEditor } from "./SpecsEditor";
import { ItemSetPicker } from "./ItemSetPicker";
import { QuickAddItem } from "../../products/components/QuickAddItem";
import { DescriptionSuggestions } from "./DescriptionSuggestions";
import { useState } from "react";
import { deviationRows, emptyLine, emptyNote, lineValuePaise, nextKey, paiseFromRupees } from "../draft";
import type { DraftComponent, DraftLine, DraftTechRow } from "../draft";
import { formatRupees } from "../format";
import { useIsOwner } from "../../auth/api";
import { useProductCosts } from "../../products/api";
import { useSettings } from "../../settings/api";

/** The small caption above each field, so every box says what it is for. */
const captionCls = "mb-1 block text-[11px] font-medium uppercase tracking-wide text-ink-2";
import type { ItemSuggestion, PrintColumn, ProductLookup } from "../../../api/types";

/**
 * Owner-only hint under a rate: the margin the typed rate leaves over the
 * landed price. Lives only on this screen; the quotation PDF never carries it.
 *
 * The percentage is on the landed price (markup), so it shows how far above
 * cost the rate is: ₹10,000 sold at ₹20,00,000 is 19,900%, not a capped ~100%.
 */
function MarginHint({ ratePaise, costPaise }: { ratePaise: number; costPaise: number | null | undefined }) {
  if (costPaise == null || costPaise <= 0 || !Number.isFinite(ratePaise) || ratePaise <= 0) return null;
  const margin = ratePaise - costPaise;
  const pct = (margin / costPaise) * 100;
  const tone = margin < 0 ? "text-red" : pct < 10 ? "text-amber" : "text-green";
  return (
    <p className="mt-1 text-[11.5px] leading-snug tabular-nums" title="Only you see this. It is not printed on the quotation.">
      <span className={`block font-semibold ${tone}`}>
        {margin < 0 ? "Loss" : "Margin"} {formatRupees(Math.abs(margin))} ·{" "}
        {pct.toLocaleString("en-IN", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%
      </span>
    </p>
  );
}

/**
 * The item table. Every cell is editable, including the rate on a line that
 * came from the catalogue — the client negotiates, and the app does not get
 * a vote on the price. Each item carries its own technical deviation rows,
 * directly under it; only the filled ones print, under that item.
 */
export function LinesEditor({
  lines,
  onChange,
  errors,
  listError,
  readOnly,
  priceOnly = false,
  layout = "pump",
  datasheetRows = [],
  printColumns = [],
  customerId = null,
}: {
  lines: DraftLine[];
  onChange: (lines: DraftLine[]) => void;
  errors: Record<string, string>;
  listError?: string;
  readOnly: boolean;
  /** A negotiation: only rates may change; no lines added or removed. */
  priceOnly?: boolean;
  /** pump: a datasheet and scope per item. spares: notes are pump-model groups. */
  layout?: "pump" | "spares";
  /** Pump offer: the datasheet's parameters, shared by every item. */
  datasheetRows?: DraftTechRow[];
  /** Spares offer: the optional columns that print, so their fields show. */
  printColumns?: PrintColumn[];
  /** The customer being quoted: their earlier items are suggested first. */
  customerId?: number | null;
}) {
  // The line whose description is being typed, for the "quoted before" list.
  const [suggestFor, setSuggestFor] = useState<string | null>(null);
  /** Fill a line from an earlier quote; every field stays editable. */
  function applySuggestion(key: string, s: ItemSuggestion) {
    const line = lines.find((l) => l.key === key);
    if (!line) return;
    update(key, {
      description: s.description,
      rate: (s.rate_paise / 100).toFixed(2).replace(/\.00$/, ""),
      hsn_code: s.hsn_code || line.hsn_code,
      unit_label: s.unit ? s.unit.charAt(0).toUpperCase() + s.unit.slice(1).toLowerCase() : line.unit_label,
      moc: s.moc || line.moc,
      part_no: s.part_no || line.part_no,
    });
    setSuggestFor(null);
  }
  const spares = layout === "spares";
  /** A group's subtotal: the items after its heading, up to the next heading. */
  function groupTotal(index: number): number {
    let sum = 0;
    for (const l of lines.slice(index + 1)) {
      if (l.kind === "note") break;
      sum += lineValuePaise(l);
    }
    return sum;
  }
  const owner = useIsOwner();
  // The free-text line being added to Inventory, if any.
  const [linking, setLinking] = useState<string | null>(null);
  // A negotiation changes prices only: everything but the rate is fixed.
  const fixed = readOnly || priceOnly;
  // New items start with the default technical deviation rows from Settings.
  const deviationDefaults = useSettings().data?.quotation_spec_defaults ?? [];
  const costs = useProductCosts(
    lines.flatMap((l) =>
      l.kind !== "product"
        ? []
        : l.components.length
          ? l.components.map((c) => c.product_id)
          : l.product_id !== null
            ? [l.product_id]
            : [],
    ),
    owner,
  );
  /** Landed cost of one unit of the line: its product, or its items x their quantities. */
  function costOf(l: DraftLine): number | null | undefined {
    if (!l.components.length) return l.product_id === null ? null : costs.get(l.product_id);
    let sum = 0;
    for (const c of l.components) {
      const each = costs.get(c.product_id);
      if (each == null) return null;
      sum += each * (Number(c.quantity) || 0);
    }
    return sum;
  }
  /**
   * Price of one unit of a multi-item line: each item's selling price x its
   * quantity, added up. null while any item's price is unknown (an item of a
   * saved quote, or one with no selling price in Inventory).
   */
  function itemsTotal(components: DraftComponent[]): number | null {
    if (!components.length) return null;
    let sum = 0;
    for (const c of components) {
      if (!c.price) return null;
      sum += c.price * (Number(c.quantity) || 0);
    }
    return sum;
  }
  /** Picking items for a line: a catalogue line's own product becomes its first item. */
  function setItems(l: DraftLine, components: DraftComponent[]) {
    const seeded =
      l.components.length === 0 && l.product_id !== null && !components.some((c) => c.product_id === l.product_id)
        ? [
            { product_id: l.product_id, name: l.description.split("\n")[0] || l.sku, quantity: "1", price: l.price },
            ...components,
          ]
        : components;
    // The rate follows the items' total until the user types a rate of their own.
    const before = itemsTotal(l.components);
    const after = itemsTotal(seeded);
    const followsItems = l.rate.trim() === "" || (before !== null && paiseFromRupees(l.rate) === before);
    update(l.key, {
      components: seeded,
      product_id: seeded.length ? null : l.product_id,
      ...(followsItems && after !== null ? { rate: (after / 100).toFixed(2).replace(/\.00$/, "") } : {}),
    });
  }
  function update(key: string, patch: Partial<DraftLine>) {
    onChange(lines.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  }

  function remove(key: string) {
    onChange(lines.filter((l) => l.key !== key));
  }

  function addProduct(p: ProductLookup) {
    onChange([
      ...lines,
      {
        key: nextKey(),
        kind: "product",
        unit_label: "Each",
        hsn_code: p.hsn_code,
        product_id: p.id,
        sku: p.sku,
        description: p.model_number ? `${p.name} ${p.model_number}` : p.name,
        quantity: "1",
        // Left empty on purpose: the dealer types the selling rate every time.
        rate: "",
        price: p.sell_price,
        service: "",
        tech: {},
        deviations: deviationRows(deviationDefaults),
        components: [],
        finalisedText: "",
      },
    ]);
  }

  const total = lines.reduce((s, l) => s + lineValuePaise(l), 0);

  // The catalogue box and add buttons sit under the last item, so the next
  // item is added right below the one before it.
  const addBar = fixed ? null : (
    <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
      <ProductPicker onPick={addProduct} />
      <div className="flex gap-2">
        <Button onClick={() => onChange([...lines, emptyLine(deviationDefaults)])}>
          <Icon name="plus" size={14} />
          Free-text line
        </Button>
        <Button onClick={() => onChange([...lines, emptyNote()])}>
          <Icon name="plus" size={14} />
          {spares ? "Pump model / group" : "Note"}
        </Button>
      </div>
    </div>
  );

  return (
    <div className="space-y-3">

      {lines.length === 0 ? (
        <p className="rounded-md border border-dashed border-line px-3 py-6 text-center text-[13px] text-ink-2">
          No items yet. Pick from the catalogue, add a free-text line, or a note such as “KSB Make”.
        </p>
      ) : (
        <ol className="space-y-2">
          {lines.map((line, i) =>
            line.kind === "note" ? (
              <li
                key={line.key}
                className={
                  spares
                    ? "grid gap-2 rounded-md border border-brand/30 bg-brand/5 p-3 md:grid-cols-[5.5rem_1fr_9rem_2.5rem] md:items-center"
                    : "grid gap-2 rounded-md border border-dashed border-line p-3 md:grid-cols-[2rem_1fr_2.5rem] md:items-start"
                }
              >
                <span className="pt-2 text-[11px] font-medium uppercase tracking-wide text-ink-2 md:pt-0">
                  {spares ? "Group" : "Note"}
                </span>
                <div>
                  <Input
                    aria-label={`Note ${i + 1}`}
                    placeholder={spares ? "Model: ETN SYT 080-065-160 EG · Sl no …" : "KSB Make"}
                    value={line.description}
                    readOnly={fixed}
                    onChange={(e) => update(line.key, { description: e.target.value })}
                  />
                  {errors[line.key] ? (
                    <p role="alert" className={fieldErrorCls}>
                      {errors[line.key]}
                    </p>
                  ) : null}
                </div>
                {spares ? (
                  <span className="text-right text-[12.5px] tabular-nums text-ink-2">
                    Subtotal <b className="font-semibold text-ink">{formatRupees(groupTotal(i))}</b>
                  </span>
                ) : null}
                {fixed ? (
                  <span />
                ) : (
                  <Button size="sm" aria-label={`Remove note ${i + 1}`} onClick={() => remove(line.key)}>
                    <Icon name="close" size={14} />
                  </Button>
                )}
              </li>
            ) : (
            <li
              key={line.key}
              className="grid gap-2 rounded-md border border-line p-3 md:grid-cols-[2rem_1fr_7rem_5rem_5rem_8rem_8rem_2.5rem] md:items-start"
            >
              <div className="flex items-center justify-between md:block md:pt-8">
                <span className="text-[13px] text-ink-2 tabular-nums">{i + 1}.</span>
                {fixed ? null : (
                  <span className="md:hidden">
                    <Button size="sm"
                    aria-label={`Remove item ${i + 1}`}
                    onClick={() => remove(line.key)}
                  >
                    <Icon name="close" size={14} />
                  </Button>
                  </span>
                )}
              </div>
              <div>
                <span className={captionCls}>Description</span>
                <Textarea
                  id={`line-desc-${line.key}`}
                  aria-label={`Item ${i + 1} description`}
                  rows={1}
                  value={line.description}
                  readOnly={fixed}
                  onFocus={() => !fixed && setSuggestFor(line.key)}
                  onBlur={() => setSuggestFor((k) => (k === line.key ? null : k))}
                  onChange={(e) => {
                    update(line.key, { description: e.target.value });
                    setSuggestFor(line.key);
                  }}
                />
                {suggestFor === line.key && !fixed ? (
                  <DescriptionSuggestions
                    label={`Item ${i + 1}`}
                    text={line.description}
                    customerId={customerId}
                    onPick={(s) => applySuggestion(line.key, s)}
                    onClose={() => setSuggestFor(null)}
                  />
                ) : null}
                <ItemSetPicker
                  label={`Item ${i + 1}`}
                  components={line.components}
                  description={line.description}
                  finalisedText={line.finalisedText}
                  locked={fixed}
                  onChange={(components) => setItems(line, components)}
                  onFinalise={(text) =>
                    // "" re-opens the items for changes; the description is left as it is.
                    update(line.key, text ? { description: text, finalisedText: text } : { finalisedText: "" })
                  }
                  onCustomize={() => document.getElementById(`line-desc-${line.key}`)?.focus()}
                />
                {line.product_id === null && line.components.length === 0 ? (
                  linking === line.key ? (
                    <QuickAddItem
                      initialName={line.description.split("\n")[0]}
                      onCancel={() => setLinking(null)}
                      onAdded={(p) => {
                        setLinking(null);
                        // The line keeps its own wording; it is now linked to the item.
                        update(line.key, { product_id: p.id, sku: p.sku, hsn_code: line.hsn_code || p.hsn_code });
                      }}
                    />
                  ) : (
                    <p className="mt-1 flex flex-wrap items-center gap-2 text-[12px] text-amber">
                      Not in Inventory: this quote cannot be accepted until the item is linked.
                      {fixed ? null : (
                        <Button size="sm" onClick={() => setLinking(line.key)}>
                          Add to inventory
                        </Button>
                      )}
                    </p>
                  )
                ) : null}
                {(line.sku && !line.components.length) || (owner && costOf(line)) || itemsTotal(line.components) !== null ? (
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    {line.sku && !line.components.length ? <Chip tone="gray">{line.sku}</Chip> : null}
                    {itemsTotal(line.components) !== null ? (
                      <span
                        className="text-[12px] tabular-nums text-ink-2"
                        title="Each item's selling price x its quantity, added up"
                      >
                        Items total <b className="font-semibold text-ink">{formatRupees(itemsTotal(line.components) ?? 0)}</b>
                      </span>
                    ) : null}
                    {owner && costOf(line) ? (
                      <span
                        className="text-[12px] tabular-nums text-ink-2"
                        title="Landed price from Inventory, for your reference. Not printed on the quotation."
                      >
                        Landed price <b className="font-semibold text-ink">{formatRupees(costOf(line) ?? 0)}</b>
                      </span>
                    ) : null}
                  </div>
                ) : null}
                {errors[line.key] ? (
                  <p role="alert" className={fieldErrorCls}>
                    {errors[line.key]}
                  </p>
                ) : null}
              </div>
              <div className="grid grid-cols-2 gap-2 md:contents">
              <label className="block">
                <span className={captionCls}>HSN/SAC</span>
                <Input
                  aria-label={`Item ${i + 1} HSN or SAC code`}
                  inputMode="numeric"
                  maxLength={15}
                  placeholder="8413"
                  value={line.hsn_code}
                  readOnly={fixed}
                  onChange={(e) => update(line.key, { hsn_code: e.target.value })}
                />
              </label>
              <label className="block">
              <span className={captionCls}>Unit</span>
              <Input
                aria-label={`Item ${i + 1} unit`}
                placeholder="Each"
                value={line.unit_label}
                readOnly={fixed}
                onChange={(e) => update(line.key, { unit_label: e.target.value })}
              />
              </label>
              <label className="block">
              <span className={captionCls}>Quantity</span>
              <Input
                aria-label={`Item ${i + 1} quantity`}
                inputMode="numeric"
                value={line.quantity}
                readOnly={fixed}
                onChange={(e) => update(line.key, { quantity: e.target.value })}
              />
              </label>
              <label className="block">
              <span className={captionCls}>Rate (₹)</span>
              <Input
                aria-label={`Item ${i + 1} rate`}
                inputMode="decimal"
                placeholder="Rate ₹"
                value={line.rate}
                readOnly={readOnly}
                onChange={(e) => update(line.key, { rate: e.target.value })}
              />
              {owner && costOf(line) != null ? (
                <MarginHint ratePaise={paiseFromRupees(line.rate)} costPaise={costOf(line)} />
              ) : null}
              </label>
              </div>
              <div className="text-right">
                <span className={captionCls}>Value</span>
                <p className="pt-2 text-[13px] tabular-nums text-ink">
                  {formatRupees(lineValuePaise(line))}
                </p>
              </div>
              {fixed ? (
                <span className="hidden md:block" />
              ) : (
                <span className="hidden md:block md:pt-6">
                  <Button size="sm"
                  aria-label={`Remove item ${i + 1}`}
                  onClick={() => remove(line.key)}
                >
                  <Icon name="close" size={14} />
                </Button>
                </span>
              )}
              {spares && printColumns.some((c) => c !== "unit") ? (
                <div className="grid gap-2 sm:grid-cols-3 md:col-start-2 md:col-end-[-1]">
                  {printColumns.includes("part_no") ? (
                    <label className="block">
                      <span className={captionCls}>Part No</span>
                      <Input
                        aria-label={`Item ${i + 1} part number`}
                        placeholder="210"
                        value={line.part_no ?? ""}
                        readOnly={fixed}
                        onChange={(e) => update(line.key, { part_no: e.target.value })}
                      />
                    </label>
                  ) : null}
                  {printColumns.includes("moc") ? (
                    <label className="block">
                      <span className={captionCls}>MOC</span>
                      <Input
                        aria-label={`Item ${i + 1} MOC`}
                        placeholder="SS 410"
                        value={line.moc ?? ""}
                        readOnly={fixed}
                        onChange={(e) => update(line.key, { moc: e.target.value })}
                      />
                    </label>
                  ) : null}
                  {printColumns.includes("delivery") ? (
                    <label className="block">
                      <span className={captionCls}>Delivery</span>
                      <Input
                        aria-label={`Item ${i + 1} delivery`}
                        placeholder="Ex stock"
                        value={line.delivery ?? ""}
                        readOnly={fixed}
                        onChange={(e) => update(line.key, { delivery: e.target.value })}
                      />
                    </label>
                  ) : null}
                </div>
              ) : null}
              {!spares ? (
                <div className="rounded-md border border-line p-3 md:col-start-2 md:col-end-[-1]">
                  <span className={captionCls}>Datasheet</span>
                  {datasheetRows.length === 0 ? (
                    <p className="text-[12px] text-ink-2">
                      Add datasheet rows above (pick a pump type) to list capacity, head, MOC and motor for this pump.
                    </p>
                  ) : (
                    <div className="grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
                      {datasheetRows.map((r) => (
                        <label key={r.key} className="grid grid-cols-[minmax(8rem,40%)_1fr] items-center gap-2">
                          <span className="truncate text-[12.5px] text-ink-2" title={r.section}>
                            {r.label || "—"}
                          </span>
                          <Input
                            aria-label={`Item ${i + 1} ${r.label}`}
                            value={line.tech[r.key] ?? ""}
                            readOnly={fixed}
                            onChange={(e) => update(line.key, { tech: { ...line.tech, [r.key]: e.target.value } })}
                          />
                        </label>
                      ))}
                    </div>
                  )}
                  <label className="mt-3 block">
                    <span className={captionCls}>Scope of supply</span>
                    <Textarea
                      aria-label={`Item ${i + 1} scope of supply`}
                      rows={2}
                      placeholder="Supply of KSB make … pump with 20 Hp 2 pole IE2 motor, base frame, coupling and guard"
                      value={line.supply_scope ?? ""}
                      readOnly={fixed}
                      onChange={(e) => update(line.key, { supply_scope: e.target.value })}
                    />
                  </label>
                </div>
              ) : null}
              <div className="rounded-md border border-line bg-hoverfill p-3 md:col-start-2 md:col-end-[-1]">
                <span className={captionCls}>Technical Deviation</span>
                <p className="mb-2 text-[12px] text-ink-2">
                  Printed under this item only, and only the rows you fill in.
                </p>
                <SpecsEditor
                  specs={line.deviations}
                  readOnly={fixed}
                  name={`Item ${i + 1} deviation`}
                  emptyText="No technical deviation on this item."
                  onChange={(deviations) => update(line.key, { deviations })}
                />
              </div>
            </li>
            ),
          )}
        </ol>
      )}

      {addBar}

      {listError ? (
        <p role="alert" className={fieldErrorCls}>
          {listError}
        </p>
      ) : null}

      <div className="flex items-baseline justify-end gap-3 text-[13px]">
        <span className="text-ink-2">Total, excluding GST</span>
        <span className="text-[15px] font-semibold tabular-nums text-ink">{formatRupees(total)}</span>
      </div>
    </div>
  );
}
