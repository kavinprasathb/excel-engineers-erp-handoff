import { useState } from "react";
import type { FormEvent } from "react";
import { Card, CardBody, CardFooter, CardHeader } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Icon } from "../../components/ui/Icon";
import { Loading } from "../../components/ui/Spinner";
import { ErrorState } from "../../components/ui/ErrorState";
import { SegmentedControl } from "../../components/ui/SegmentedControl";
import { errorMessage } from "../../lib/errors";
import { useToast } from "../../components/ui/toast-context";
import { useSettings, useUpdateSettings } from "./api";
import { QUOTATION_TYPES } from "../../api/types";
import type { QuotationTermsDefaults, QuotationType, Settings } from "../../api/types";

type Row = { key: string; label: string; text: string };
type Form = Record<QuotationType, Row[]>;

let seq = 0;
const key = () => `t${++seq}`;

function pick(settings: Settings): Form {
  const out = {} as Form;
  for (const t of QUOTATION_TYPES) {
    out[t.value] = (settings.quotation_terms_defaults[t.value] ?? []).map((r) => ({
      key: key(),
      ...r,
    }));
  }
  return out;
}

/**
 * The terms a new quotation starts with, per type. Editing here changes
 * future quotes only — every quote carries its own copy.
 */
export function QuotationTermsCard() {
  const toast = useToast();
  const settings = useSettings();
  const update = useUpdateSettings();
  const [type, setType] = useState<QuotationType>("spares");
  const [form, setForm] = useState<Form | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [seededFrom, setSeededFrom] = useState<Settings | null>(null);
  if (settings.data && settings.data !== seededFrom) {
    setSeededFrom(settings.data);
    setForm(pick(settings.data));
  }

  function rows(): Row[] {
    return form?.[type] ?? [];
  }

  function setRows(next: Row[]) {
    setForm((f) => (f ? { ...f, [type]: next } : f));
  }

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!form) return;
    const out = {} as QuotationTermsDefaults;
    for (const t of QUOTATION_TYPES) {
      out[t.value] = form[t.value]
        .filter((r) => r.label.trim() !== "")
        .map((r) => ({ label: r.label.trim(), text: r.text.trim() }));
    }
    setError(null);
    update.mutate(
      { quotation_terms_defaults: out },
      {
        onSuccess: () => toast.success("Default terms saved."),
        onError: (err) => setError(errorMessage(err)),
      },
    );
  }

  if (settings.isError) {
    return (
      <ErrorState
        title="Could not load the default terms"
        error={settings.error}
        onRetry={() => settings.refetch()}
      />
    );
  }

  return (
    <Card>
      <form onSubmit={onSubmit} noValidate>
        <CardHeader
          title="Quotation terms"
          description="What a new quotation starts with. Existing quotations keep their own."
        />
        <CardBody className="space-y-4">
          {!form ? (
            <Loading />
          ) : (
            <>
              <SegmentedControl
                label="Quotation type"
                value={type}
                onChange={setType}
                options={QUOTATION_TYPES.map((t) => ({ value: t.value, label: t.label }))}
                fullWidth
              />
              <ul className="space-y-2">
                {rows().map((r, i) => (
                  <li key={r.key} className="grid gap-2 md:grid-cols-[11rem_1fr_2.5rem]">
                    <Input
                      aria-label={`Term ${i + 1} label`}
                      placeholder="Label"
                      value={r.label}
                      onChange={(e) =>
                        setRows(rows().map((x) => (x.key === r.key ? { ...x, label: e.target.value } : x)))
                      }
                    />
                    <Input
                      aria-label={`Term ${i + 1} text`}
                      placeholder="Text"
                      value={r.text}
                      onChange={(e) =>
                        setRows(rows().map((x) => (x.key === r.key ? { ...x, text: e.target.value } : x)))
                      }
                    />
                    <Button
                      size="sm"
                      aria-label={`Remove term ${i + 1}`}
                      onClick={() => setRows(rows().filter((x) => x.key !== r.key))}
                    >
                      <Icon name="close" size={14} />
                    </Button>
                  </li>
                ))}
              </ul>
              <Button
                size="sm"
                onClick={() => setRows([...rows(), { key: key(), label: "", text: "" }])}
              >
                <Icon name="plus" size={14} />
                Add a term
              </Button>
            </>
          )}
          {error ? (
            <p className="text-[13px] text-red" role="alert">
              {error}
            </p>
          ) : null}
        </CardBody>
        <CardFooter>
          <Button type="submit" variant="primary" loading={update.isPending} disabled={!form}>
            Save default terms
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
