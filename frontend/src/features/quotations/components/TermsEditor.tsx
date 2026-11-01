import { Button } from "../../../components/ui/Button";
import { Input } from "../../../components/ui/Input";
import { Icon } from "../../../components/ui/Icon";
import { nextKey } from "../draft";
import type { DraftTerm } from "../draft";

/**
 * Commercial terms as a checklist. Every default is present and ticked; an
 * unticked one stays on the quote (so it can be ticked back) but is left off
 * the letter. Label and text are both editable in place.
 */
export function TermsEditor({
  terms,
  onChange,
  readOnly,
}: {
  terms: DraftTerm[];
  onChange: (terms: DraftTerm[]) => void;
  readOnly: boolean;
}) {
  function update(key: string, patch: Partial<DraftTerm>) {
    onChange(terms.map((t) => (t.key === key ? { ...t, ...patch } : t)));
  }

  return (
    <div className="space-y-2">
      {terms.length === 0 ? (
        <p className="text-[13px] text-ink-2">No terms on this quotation.</p>
      ) : (
        <ul className="space-y-2">
          {terms.map((t) => (
            <li
              key={t.key}
              className="grid gap-2 md:grid-cols-[11rem_1fr_2.5rem] md:items-center"
            >
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  aria-label={`Include ${t.label || "term"}`}
                  className="size-5 shrink-0 accent-brand md:size-4"
                  checked={t.included}
                  disabled={readOnly}
                  onChange={(e) => update(t.key, { included: e.target.checked })}
                />
                <Input
                  aria-label="Term label"
                  value={t.label}
                  readOnly={readOnly}
                  className={t.included ? "" : "opacity-60"}
                  onChange={(e) => update(t.key, { label: e.target.value })}
                />
                {readOnly ? null : (
                  <span className="md:hidden">
                    <Button size="sm"
                    aria-label={`Remove ${t.label || "term"}`}
                    onClick={() => onChange(terms.filter((x) => x.key !== t.key))}
                  >
                    <Icon name="close" size={14} />
                  </Button>
                  </span>
                )}
              </div>
              <Input
                aria-label={`${t.label || "Term"} text`}
                value={t.text}
                readOnly={readOnly}
                className={t.included ? "" : "opacity-60"}
                onChange={(e) => update(t.key, { text: e.target.value })}
              />
              {readOnly ? (
                <span className="hidden md:block" />
              ) : (
                <span className="hidden md:block">
                  <Button size="sm"
                  aria-label={`Remove ${t.label || "term"}`}
                  onClick={() => onChange(terms.filter((x) => x.key !== t.key))}
                >
                  <Icon name="close" size={14} />
                </Button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {readOnly ? null : (
        <Button
          size="sm"
          onClick={() =>
            onChange([...terms, { key: nextKey(), label: "", text: "", included: true }])
          }
        >
          <Icon name="plus" size={14} />
          Add a term
        </Button>
      )}
    </div>
  );
}
