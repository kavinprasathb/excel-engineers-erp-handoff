import { Button } from "../../../components/ui/Button";
import { Input } from "../../../components/ui/Input";
import { Icon } from "../../../components/ui/Icon";
import { emptySpec } from "../draft";
import type { DraftSpec } from "../draft";

/**
 * An item's technical deviation: `label : value` rows, printed in this order
 * under the item when filled. Nothing here is fixed — the defaults only save
 * typing. `name` prefixes every accessible label ("Item 2 deviation row 1").
 */
export function SpecsEditor({
  specs,
  onChange,
  readOnly,
  name,
  emptyText,
}: {
  specs: DraftSpec[];
  onChange: (specs: DraftSpec[]) => void;
  readOnly: boolean;
  name: string;
  emptyText: string;
}) {
  function update(key: string, patch: Partial<DraftSpec>) {
    onChange(specs.map((s) => (s.key === key ? { ...s, ...patch } : s)));
  }

  function move(key: string, delta: -1 | 1) {
    const i = specs.findIndex((s) => s.key === key);
    const j = i + delta;
    if (i < 0 || j < 0 || j >= specs.length) return;
    const next = [...specs];
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  }

  return (
    <div className="space-y-2">
      {specs.length === 0 ? (
        <p className="text-[13px] text-ink-2">{emptyText}</p>
      ) : (
        <ul className="space-y-2">
          {specs.map((s, i) => (
            <li key={s.key} className="grid gap-2 md:grid-cols-[13rem_1fr_auto] md:items-center">
              <Input
                aria-label={`${name} row ${i + 1} label`}
                placeholder="Pump Model"
                value={s.label}
                readOnly={readOnly}
                onChange={(e) => update(s.key, { label: e.target.value })}
              />
              <Input
                aria-label={`${name} ${s.label || `row ${i + 1}`} value`}
                value={s.value}
                readOnly={readOnly}
                onChange={(e) => update(s.key, { value: e.target.value })}
              />
              {readOnly ? (
                <span />
              ) : (
                <div className="flex gap-1">
                  <Button
                    size="sm"
                    aria-label={`Move ${name} row ${i + 1} up`}
                    disabled={i === 0}
                    onClick={() => move(s.key, -1)}
                  >
                    <Icon name="chevronUp" size={14} />
                  </Button>
                  <Button
                    size="sm"
                    aria-label={`Move ${name} row ${i + 1} down`}
                    disabled={i === specs.length - 1}
                    onClick={() => move(s.key, 1)}
                  >
                    <Icon name="chevronDown" size={14} />
                  </Button>
                  <Button
                    size="sm"
                    aria-label={`Remove ${name} row ${i + 1}`}
                    onClick={() => onChange(specs.filter((x) => x.key !== s.key))}
                  >
                    <Icon name="close" size={14} />
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {readOnly ? null : (
        <Button size="sm" aria-label={`Add a ${name} row`} onClick={() => onChange([...specs, emptySpec()])}>
          <Icon name="plus" size={14} />
          Add a row
        </Button>
      )}
    </div>
  );
}
