import { useState } from "react";
import { Button } from "../../../components/ui/Button";
import { Input } from "../../../components/ui/Input";
import { Select } from "../../../components/ui/Select";
import { Textarea } from "../../../components/ui/Textarea";
import { Icon } from "../../../components/ui/Icon";
import { formatRupees } from "../format";
import { ProductPicker } from "./ProductPicker";
import { emptyLine, lineValuePaise, nextKey } from "../draft";
import type { DraftLine, DraftTechRow } from "../draft";
import { TECH_TEMPLATES } from "../techTemplates";
import type { ProductLookup } from "../../../api/types";

const cell = "border border-line p-1 align-top";
const fieldErrorCls = "mt-1 text-[12px] text-red";

/**
 * The technical offer sheet: one column per pump, one row per technical
 * parameter, then quantity, unit price and total for each column, as in the
 * Excel offers sent to technical customers. Each column is an ordinary
 * quotation line underneath (product, quantity, rate), so stock, orders,
 * revisions, negotiations and the reports work exactly as for the item list.
 *
 * In a negotiation only the unit prices can change; everything else is fixed.
 */
export function TechSheetEditor({
  rows,
  lines,
  scope,
  priceLabel = "",
  onRows,
  onLines,
  onScope,
  onPriceLabel = () => {},
  errors,
  listError,
  readOnly,
  priceOnly = false,
}: {
  rows: DraftTechRow[];
  lines: DraftLine[];
  scope: string;
  /** What the unit price covers: "Pump with accessories (without motor)". */
  priceLabel?: string;
  onRows: (rows: DraftTechRow[]) => void;
  onLines: (lines: DraftLine[]) => void;
  onScope: (scope: string) => void;
  onPriceLabel?: (label: string) => void;
  errors: Record<string, string>;
  listError?: string;
  readOnly: boolean;
  priceOnly?: boolean;
}) {
  const fixed = readOnly || priceOnly;
  const [template, setTemplate] = useState("");
  // Notes have no place in a grid; only item lines are columns.
  const cols = lines.filter((l) => l.kind !== "note");
  const total = cols.reduce((s, l) => s + lineValuePaise(l), 0);
  // The duty point printed under each heading, from the capacity and head rows.
  const capRow = rows.find((r) => /capacity|flow|discharge/i.test(r.label));
  const headRow = rows.find((r) => /head/i.test(r.label) && !/shut/i.test(r.label));
  function duty(l: DraftLine): string {
    const q = capRow ? (l.tech[capRow.key] ?? "").trim() : "";
    const h = headRow ? (l.tech[headRow.key] ?? "").trim() : "";
    return q && h ? `${q} m³/hr @ ${h} m` : "";
  }

  function update(key: string, patch: Partial<DraftLine>) {
    onLines(lines.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  }
  function setValue(line: DraftLine, rowKey: string, value: string) {
    update(line.key, { tech: { ...line.tech, [rowKey]: value } });
  }
  function copyAcross(rowKey: string) {
    const first = cols[0]?.tech[rowKey] ?? "";
    onLines(lines.map((l) => (l.kind === "note" ? l : { ...l, tech: { ...l.tech, [rowKey]: first } })));
  }
  function addProduct(p: ProductLookup) {
    onLines([
      ...lines,
      {
        ...emptyLine(),
        product_id: p.id,
        sku: p.sku,
        hsn_code: p.hsn_code,
        description: p.model_number ? `${p.name} ${p.model_number}` : p.name,
        price: p.sell_price,
        deviations: [],
      },
    ]);
  }
  function addTemplate(name: string) {
    const t = TECH_TEMPLATES.find((x) => x.name === name);
    if (!t) return;
    // Rows already on the sheet stay, with their values; only missing ones are added.
    const have = new Set(rows.map((r) => r.label.trim().toLowerCase()));
    onRows([
      ...rows,
      ...t.rows
        .filter((r) => !have.has(r.label.toLowerCase()))
        .map((r) => ({ key: nextKey(), section: r.section, label: r.label })),
    ]);
    setTemplate("");
  }
  function moveRow(i: number, by: number) {
    const j = i + by;
    if (j < 0 || j >= rows.length) return;
    const next = [...rows];
    [next[i], next[j]] = [next[j], next[i]];
    onRows(next);
  }

  return (
    <div className="space-y-3">
      {fixed ? null : (
        <div className="flex flex-wrap items-end gap-2">
          <label className="block">
            <span className="mb-1 block text-[12px] text-ink-2">Rows from template</span>
            <Select
              aria-label="Rows from template"
              value={template}
              onChange={(e) => addTemplate(e.target.value)}
            >
              <option value="">Choose a pump type…</option>
              {TECH_TEMPLATES.map((t) => (
                <option key={t.name} value={t.name}>
                  {t.name}
                </option>
              ))}
            </Select>
          </label>
          <Button onClick={() => onRows([...rows, { key: nextKey(), section: rows.at(-1)?.section ?? "", label: "" }])}>
            <Icon name="plus" size={14} />
            Row
          </Button>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[40rem] border-collapse text-[13px]">
          <thead>
            <tr>
              <th className={`${cell} w-64 bg-hoverfill text-left font-semibold text-ink`}>Parameter</th>
              {cols.map((l, i) => (
                <th key={l.key} className={`${cell} min-w-[10rem] bg-hoverfill`}>
                  <div className="flex items-center gap-1">
                    <Input
                      aria-label={`Column ${i + 1} service`}
                      placeholder={`Service ${i + 1}, e.g. UF Feed`}
                      value={l.service}
                      readOnly={fixed}
                      onChange={(e) => update(l.key, { service: e.target.value })}
                    />
                    {fixed ? null : (
                      <Button
                        size="sm"
                        aria-label={`Remove column ${i + 1}`}
                        onClick={() => onLines(lines.filter((x) => x.key !== l.key))}
                      >
                        <Icon name="close" size={14} />
                      </Button>
                    )}
                  </div>
                  {duty(l) ? (
                    <p className="mt-1 text-left text-[11.5px] font-normal tabular-nums text-ink-2">{duty(l)}</p>
                  ) : null}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className={`${cell} font-medium text-ink`}>Pump Model</td>
              {cols.map((l, i) => (
                <td key={l.key} className={cell}>
                  <Input
                    aria-label={`Column ${i + 1} pump model`}
                    value={l.description}
                    readOnly={fixed}
                    onChange={(e) => update(l.key, { description: e.target.value })}
                  />
                  {errors[l.key] ? (
                    <p role="alert" className={fieldErrorCls}>
                      {errors[l.key]}
                    </p>
                  ) : null}
                </td>
              ))}
            </tr>
            {rows.map((r, ri) => {
              const newSection = r.section && r.section !== rows[ri - 1]?.section;
              return [
                newSection ? (
                  <tr key={`${r.key}-s`}>
                    <td colSpan={cols.length + 1} className={`${cell} bg-hoverfill font-semibold text-ink`}>
                      {r.section}
                    </td>
                  </tr>
                ) : null,
                <tr key={r.key}>
                  <td className={cell}>
                    {fixed ? (
                      <span className="block px-1 py-1.5 text-ink">{r.label}</span>
                    ) : (
                      <div className="space-y-1">
                        <div className="flex items-center gap-1">
                          <Input
                            aria-label={`Row ${ri + 1} parameter`}
                            placeholder="Parameter"
                            value={r.label}
                            onChange={(e) => onRows(rows.map((x) => (x.key === r.key ? { ...x, label: e.target.value } : x)))}
                          />
                          <Button size="sm" aria-label={`Move row ${ri + 1} up`} onClick={() => moveRow(ri, -1)}>
                            ↑
                          </Button>
                          <Button size="sm" aria-label={`Move row ${ri + 1} down`} onClick={() => moveRow(ri, 1)}>
                            ↓
                          </Button>
                          <Button
                            size="sm"
                            aria-label={`Remove row ${ri + 1}`}
                            onClick={() => onRows(rows.filter((x) => x.key !== r.key))}
                          >
                            <Icon name="close" size={14} />
                          </Button>
                        </div>
                        <div className="flex items-center gap-1">
                          <Input
                            aria-label={`Row ${ri + 1} section`}
                            placeholder="Section (optional)"
                            className="text-[12px]"
                            value={r.section}
                            onChange={(e) => onRows(rows.map((x) => (x.key === r.key ? { ...x, section: e.target.value } : x)))}
                          />
                          {cols.length > 1 ? (
                            <Button
                              size="sm"
                              aria-label={`Copy row ${ri + 1} to all columns`}
                              title="Copy the first column's value to every column"
                              onClick={() => copyAcross(r.key)}
                            >
                              Copy →
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    )}
                  </td>
                  {cols.map((l, ci) => (
                    <td key={l.key} className={cell}>
                      <Input
                        aria-label={`Column ${ci + 1} ${r.label || `row ${ri + 1}`}`}
                        value={l.tech[r.key] ?? ""}
                        readOnly={fixed}
                        onChange={(e) => setValue(l, r.key, e.target.value)}
                      />
                    </td>
                  ))}
                </tr>,
              ];
            })}
            <tr>
              <td className={`${cell} bg-hoverfill font-semibold text-ink`} colSpan={cols.length + 1}>
                Price
              </td>
            </tr>
            <tr>
              <td className={`${cell} text-ink`}>Qty</td>
              {cols.map((l, i) => (
                <td key={l.key} className={cell}>
                  <Input
                    aria-label={`Column ${i + 1} quantity`}
                    inputMode="numeric"
                    value={l.quantity}
                    readOnly={fixed}
                    onChange={(e) => update(l.key, { quantity: e.target.value })}
                  />
                </td>
              ))}
            </tr>
            <tr>
              <td className={`${cell} text-ink`}>
                <Input
                  aria-label="What the price covers"
                  placeholder="Pump with accessories (without motor)"
                  className="text-[12px]"
                  value={priceLabel}
                  readOnly={fixed}
                  onChange={(e) => onPriceLabel(e.target.value)}
                />
                <span className="mt-1 block text-[12px] text-ink-2">Unit Price (₹)</span>
              </td>
              {cols.map((l, i) => (
                <td key={l.key} className={cell}>
                  <Input
                    aria-label={`Column ${i + 1} unit price`}
                    inputMode="decimal"
                    placeholder="Rate ₹"
                    value={l.rate}
                    readOnly={readOnly}
                    onChange={(e) => update(l.key, { rate: e.target.value })}
                  />
                </td>
              ))}
            </tr>
            <tr>
              <td className={`${cell} font-semibold text-ink`}>Total Price</td>
              {cols.map((l) => (
                <td key={l.key} className={`${cell} text-right font-semibold tabular-nums text-ink`}>
                  {formatRupees(lineValuePaise(l))}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>

      {fixed ? null : (
        <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
          <ProductPicker onPick={addProduct} />
          <Button onClick={() => onLines([...lines, { ...emptyLine(), deviations: [] }])}>
            <Icon name="plus" size={14} />
            Blank column
          </Button>
        </div>
      )}

      {listError ? (
        <p role="alert" className={fieldErrorCls}>
          {listError}
        </p>
      ) : null}

      <label className="block">
        <span className="mb-1 block text-[12px] text-ink-2">Scope of supply</span>
        <Textarea
          aria-label="Scope of supply"
          rows={2}
          placeholder="Supply of KSB make ETN pump with seal + MS fabricated base frame + coupling. Motor not in our scope."
          value={scope}
          readOnly={fixed}
          onChange={(e) => onScope(e.target.value)}
        />
      </label>

      <div className="flex items-baseline justify-end gap-3 text-[13px]">
        <span className="text-ink-2">Total, excluding GST</span>
        <span className="text-[15px] font-semibold tabular-nums text-ink">{formatRupees(total)}</span>
      </div>
    </div>
  );
}
