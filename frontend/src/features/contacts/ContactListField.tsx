import { useId } from "react";
import { Input } from "../../components/ui/Input";
import { Button } from "../../components/ui/Button";
import { Label } from "../../components/ui/Label";
import { fieldErrorCls } from "../../components/ui/styles";
import { MAX_CONTACTS, contactError } from "./contactValues";
import type { ContactKind } from "./contactValues";

/**
 * One input per email or phone number, with a remove button on each and an
 * "add" button underneath. Always shows at least one (possibly empty) row.
 */
export function ContactListField({
  kind,
  label,
  values,
  onChange,
  showErrors,
}: {
  kind: ContactKind;
  label: string;
  values: readonly string[];
  onChange: (values: string[]) => void;
  /** Only flag bad rows after the first submit attempt. */
  showErrors: boolean;
}) {
  const id = useId();
  const rows = values.length ? values : [""];
  const noun = kind === "email" ? "email" : "phone number";

  function set(index: number, value: string) {
    const next = [...rows];
    next[index] = value;
    onChange(next);
  }

  function remove(index: number) {
    onChange(rows.filter((_, i) => i !== index));
  }

  return (
    <div>
      <Label htmlFor={`${id}-0`}>{label}</Label>
      <div className="space-y-2">
        {rows.map((value, index) => {
          const error = showErrors ? contactError(kind, value) : undefined;
          const errorId = `${id}-${index}-error`;
          return (
            <div key={index}>
              <div className="flex items-center gap-2">
                <Input
                  id={`${id}-${index}`}
                  aria-label={`${label} ${index + 1}`}
                  aria-describedby={error ? errorId : undefined}
                  invalid={Boolean(error)}
                  type={kind === "email" ? "email" : "tel"}
                  inputMode={kind === "email" ? "email" : "tel"}
                  value={value}
                  onChange={(e) => set(index, e.target.value)}
                />
                <button
                  type="button"
                  onClick={() => remove(index)}
                  aria-label={`Remove ${noun} ${index + 1}`}
                  title={`Remove ${noun}`}
                  disabled={rows.length === 1 && !value}
                  className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-[18px] leading-none text-ink-2 hover:bg-hoverfill hover:text-ink disabled:opacity-40"
                >
                  ×
                </button>
              </div>
              {error ? (
                <p id={errorId} role="alert" className={fieldErrorCls}>
                  {error}
                </p>
              ) : null}
            </div>
          );
        })}
      </div>
      {rows.length < MAX_CONTACTS ? (
        <Button size="sm" variant="ghost" className="mt-2" onClick={() => onChange([...rows, ""])}>
          {kind === "email" ? "+ Add Email" : "+ Add Mobile"}
        </Button>
      ) : null}
    </div>
  );
}
