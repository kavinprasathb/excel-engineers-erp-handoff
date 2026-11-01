import { useState } from "react";
import type { FormEvent } from "react";
import { Card, CardBody, CardFooter, CardHeader } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { FormField } from "../../components/ui/FormField";
import { Input } from "../../components/ui/Input";
import { Loading } from "../../components/ui/Spinner";
import { ErrorState } from "../../components/ui/ErrorState";
import { errorMessage } from "../../lib/errors";
import { useToast } from "../../components/ui/toast-context";
import { bpToPercent, percentToBp } from "../../lib/format";
import { useSettings, useUpdateSettings } from "./api";
import type { Settings } from "../../api/types";

interface Errors {
  company_name?: string;
  low_stock_threshold?: string;
  default_gst_rate_bp?: string;
}

export function CompanyCard() {
  const toast = useToast();
  const settings = useSettings();
  const update = useUpdateSettings();

  const [name, setName] = useState("");
  const [threshold, setThreshold] = useState("");
  // Held as the percentage the user types; converted to basis points only on
  // submit, so "18.5" survives a round trip without float drift in the field.
  const [gstPercent, setGstPercent] = useState("");
  const [errors, setErrors] = useState<Errors>({});

  // Seed the fields from the server the first time the data arrives, and
  // again if it is refetched into something different. Done during render
  // rather than in an effect so the form never paints one frame empty.
  const [seededFrom, setSeededFrom] = useState<Settings | null>(null);
  if (settings.data && settings.data !== seededFrom) {
    setSeededFrom(settings.data);
    setName(settings.data.company_name);
    setThreshold(String(settings.data.low_stock_threshold));
    setGstPercent(String(bpToPercent(settings.data.default_gst_rate_bp)));
  }

  function validate(): Errors {
    const e: Errors = {};
    if (!name.trim()) e.company_name = "Enter a company name.";

    const t = Number(threshold);
    if (!Number.isInteger(t) || t < 0) {
      e.low_stock_threshold = "Enter a whole number, 0 or more.";
    }

    const g = Number(gstPercent);
    if (!Number.isFinite(g) || g < 0 || g > 100) {
      e.default_gst_rate_bp = "Enter a percentage between 0 and 100.";
    }
    return e;
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    update.mutate(
      {
        company_name: name.trim(),
        low_stock_threshold: Number(threshold),
        default_gst_rate_bp: percentToBp(Number(gstPercent)),
      },
      {
        onSuccess: () => toast.success("Company settings saved."),
        onError: (error) => setErrors({ company_name: errorMessage(error) }),
      },
    );
  }

  if (settings.isPending) {
    return (
      <Card>
        <CardHeader title="Company" />
        <CardBody>
          <Loading />
        </CardBody>
      </Card>
    );
  }

  if (settings.isError) {
    return (
      <ErrorState
        title="Could not load company settings"
        error={settings.error}
        onRetry={() => settings.refetch()}
      />
    );
  }

  return (
    <Card>
      <form onSubmit={onSubmit} noValidate>
        <CardHeader
          title="Company"
          description="Used on documents and to decide what counts as low stock."
        />
        <CardBody className="space-y-4">
          <FormField label="Company name" required error={errors.company_name}>
            {(props) => (
              <Input {...props} value={name} onChange={(e) => setName(e.target.value)} />
            )}
          </FormField>

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              label="Low-stock threshold"
              required
              error={errors.low_stock_threshold}
              hint="Items at or below this count are flagged."
            >
              {(props) => (
                <Input
                  {...props}
                  type="number"
                  inputMode="numeric"
                  min={0}
                  step={1}
                  className="tabular-nums"
                  value={threshold}
                  onChange={(e) => setThreshold(e.target.value)}
                />
              )}
            </FormField>

            <FormField
              label="Default GST rate (%)"
              required
              error={errors.default_gst_rate_bp}
              hint="Applied to new products unless overridden."
            >
              {(props) => (
                <Input
                  {...props}
                  type="number"
                  inputMode="decimal"
                  min={0}
                  max={100}
                  step="0.01"
                  className="tabular-nums"
                  value={gstPercent}
                  onChange={(e) => setGstPercent(e.target.value)}
                />
              )}
            </FormField>
          </div>
        </CardBody>
        <CardFooter>
          <Button type="submit" variant="primary" loading={update.isPending}>
            Save changes
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
