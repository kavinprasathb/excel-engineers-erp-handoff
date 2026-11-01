import { useState } from "react";
import type { FormEvent } from "react";
import { Card, CardBody, CardFooter, CardHeader } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Icon } from "../../components/ui/Icon";
import { Loading } from "../../components/ui/Spinner";
import { ErrorState } from "../../components/ui/ErrorState";
import { errorMessage } from "../../lib/errors";
import { useToast } from "../../components/ui/toast-context";
import { useSettings, useUpdateSettings } from "./api";
import type { Settings } from "../../api/types";

type Row = { key: string; label: string; value: string };

let seq = 0;
const key = () => `s${++seq}`;

function pick(settings: Settings): Row[] {
  return settings.quotation_spec_defaults.map((r) => ({ key: key(), ...r }));
}

/**
 * The technical deviation rows every new quotation item starts with. Values
 * are usually blank here — the label is the point — but a fixed value such
 * as "Please refer enclosed technical data sheet" can live here too.
 */
export function QuotationSpecsCard() {
  const toast = useToast();
  const settings = useSettings();
  const update = useUpdateSettings();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [seededFrom, setSeededFrom] = useState<Settings | null>(null);
  if (settings.data && settings.data !== seededFrom) {
    setSeededFrom(settings.data);
    setRows(pick(settings.data));
  }

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!rows) return;
    setError(null);
    update.mutate(
      {
        quotation_spec_defaults: rows
          .filter((r) => r.label.trim() !== "")
          .map((r) => ({ label: r.label.trim(), value: r.value.trim() })),
      },
      {
        onSuccess: () => toast.success("Default technical deviation rows saved."),
        onError: (err) => setError(errorMessage(err)),
      },
    );
  }

  if (settings.isError) {
    return (
      <ErrorState
        title="Could not load the technical deviation rows"
        error={settings.error}
        onRetry={() => settings.refetch()}
      />
    );
  }

  return (
    <Card>
      <form onSubmit={onSubmit} noValidate>
        <CardHeader
          title="Technical deviation rows"
          description="The rows every new quotation item starts with. Existing items keep their own."
        />
        <CardBody className="space-y-3">
          {!rows ? (
            <Loading />
          ) : (
            <>
              <ul className="space-y-2">
                {rows.map((r, i) => (
                  <li key={r.key} className="grid gap-2 md:grid-cols-[13rem_1fr_2.5rem]">
                    <Input
                      aria-label={`Row ${i + 1} label`}
                      placeholder="Label"
                      value={r.label}
                      onChange={(e) =>
                        setRows(rows.map((x) => (x.key === r.key ? { ...x, label: e.target.value } : x)))
                      }
                    />
                    <Input
                      aria-label={`Row ${i + 1} default value`}
                      placeholder="Default value (usually blank)"
                      value={r.value}
                      onChange={(e) =>
                        setRows(rows.map((x) => (x.key === r.key ? { ...x, value: e.target.value } : x)))
                      }
                    />
                    <Button
                      size="sm"
                      aria-label={`Remove row ${i + 1}`}
                      onClick={() => setRows(rows.filter((x) => x.key !== r.key))}
                    >
                      <Icon name="close" size={14} />
                    </Button>
                  </li>
                ))}
              </ul>
              <Button size="sm" onClick={() => setRows([...rows, { key: key(), label: "", value: "" }])}>
                <Icon name="plus" size={14} />
                Add a row
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
          <Button type="submit" variant="primary" loading={update.isPending} disabled={!rows}>
            Save technical deviation rows
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
