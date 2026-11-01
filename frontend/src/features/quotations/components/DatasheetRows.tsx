import { useState } from "react";
import { Button } from "../../../components/ui/Button";
import { Input } from "../../../components/ui/Input";
import { Select } from "../../../components/ui/Select";
import { Icon } from "../../../components/ui/Icon";
import { nextKey } from "../draft";
import type { DraftTechRow } from "../draft";
import { TECH_TEMPLATES } from "../techTemplates";

/**
 * The datasheet's rows for a pump offer: which parameters each pump lists
 * (capacity, head, MOC, motor...). Shared by every pump in the quotation and
 * by the technical sheet, so switching between the two keeps the data. Only
 * rows that are filled in for a pump print for it.
 */
export function DatasheetRows({
  rows,
  onChange,
  readOnly,
}: {
  rows: DraftTechRow[];
  onChange: (rows: DraftTechRow[]) => void;
  readOnly: boolean;
}) {
  const [editing, setEditing] = useState(false);

  function addTemplate(name: string) {
    const t = TECH_TEMPLATES.find((x) => x.name === name);
    if (!t) return;
    const have = new Set(rows.map((r) => r.label.trim().toLowerCase()));
    onChange([
      ...rows,
      ...t.rows
        .filter((r) => !have.has(r.label.toLowerCase()))
        .map((r) => ({ key: nextKey(), section: r.section, label: r.label })),
    ]);
  }

  return (
    <div className="rounded-lg border border-line bg-hoverfill/60 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[13px] font-semibold text-ink">Datasheet rows</span>
        <span className="text-[12px] text-ink-2">
          {rows.length ? `${rows.length} parameters for every pump; only filled ones print.` : "None yet: pick a pump type."}
        </span>
        {readOnly ? null : (
          <span className="ml-auto flex flex-wrap items-center gap-2">
            <Select
              aria-label="Datasheet template"
              value=""
              onChange={(e) => addTemplate(e.target.value)}
            >
              <option value="">Add rows for a pump type…</option>
              {TECH_TEMPLATES.map((t) => (
                <option key={t.name} value={t.name}>
                  {t.name}
                </option>
              ))}
            </Select>
            <Button size="sm" onClick={() => setEditing((v) => !v)} aria-expanded={editing}>
              {editing ? "Done" : "Edit rows"}
            </Button>
          </span>
        )}
      </div>
      {editing && !readOnly ? (
        <div className="mt-3 space-y-1.5">
          {rows.map((r, i) => (
            <div key={r.key} className="grid gap-1.5 sm:grid-cols-[1fr_1fr_auto]">
              <Input
                aria-label={`Datasheet row ${i + 1} parameter`}
                placeholder="Parameter, e.g. Capacity (m³/hr)"
                value={r.label}
                onChange={(e) => onChange(rows.map((x) => (x.key === r.key ? { ...x, label: e.target.value } : x)))}
              />
              <Input
                aria-label={`Datasheet row ${i + 1} section`}
                placeholder="Section, e.g. Material Of Construction"
                value={r.section}
                onChange={(e) => onChange(rows.map((x) => (x.key === r.key ? { ...x, section: e.target.value } : x)))}
              />
              <Button
                size="sm"
                aria-label={`Remove datasheet row ${i + 1}`}
                onClick={() => onChange(rows.filter((x) => x.key !== r.key))}
              >
                <Icon name="close" size={14} />
              </Button>
            </div>
          ))}
          <Button
            size="sm"
            onClick={() => onChange([...rows, { key: nextKey(), section: rows.at(-1)?.section ?? "", label: "" }])}
          >
            <Icon name="plus" size={14} />
            Row
          </Button>
        </div>
      ) : null}
    </div>
  );
}
