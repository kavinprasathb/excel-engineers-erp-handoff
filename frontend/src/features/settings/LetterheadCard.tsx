import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { Card, CardBody, CardFooter, CardHeader } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { FormField } from "../../components/ui/FormField";
import { Input } from "../../components/ui/Input";
import { Loading } from "../../components/ui/Spinner";
import { ErrorState } from "../../components/ui/ErrorState";
import { eyebrowCls } from "../../components/ui/styles";
import { errorMessage } from "../../lib/errors";
import { useToast } from "../../components/ui/toast-context";
import { useSettings, useUpdateSettings } from "./api";
import type { Settings } from "../../api/types";

/** Exactly the letterhead half of Settings, and nothing else. */
type LetterheadKey =
  | "company_address_line1"
  | "company_address_line2"
  | "company_city"
  | "company_state"
  | "company_pincode"
  | "company_gstin"
  | "company_phone"
  | "company_mobile"
  | "company_email"
  | "signatory_name"
  | "signatory_designation";

const KEYS: readonly LetterheadKey[] = [
  "company_address_line1",
  "company_address_line2",
  "company_city",
  "company_state",
  "company_pincode",
  "company_gstin",
  "company_phone",
  "company_mobile",
  "company_email",
  "signatory_name",
  "signatory_designation",
];

type Form = Record<LetterheadKey, string>;
type Errors = Partial<Record<LetterheadKey | "form", string>>;

function pick(settings: Settings): Form {
  return Object.fromEntries(KEYS.map((k) => [k, settings[k]])) as Form;
}

/**
 * The letterhead every printed document carries. Held here rather than in a
 * template because it demonstrably changes — the company's 2020 offers carry
 * a different phone number from its 2026 ones — and changing it should be an
 * admin filling in a form, not a developer redeploying.
 *
 * Every field may legitimately be blank: "" means "do not print this line".
 * Only the GSTIN is checked for shape, because a wrong one on a tax document
 * is a real problem and a missing one is merely an empty line.
 */
export function LetterheadCard() {
  const toast = useToast();
  const settings = useSettings();
  const update = useUpdateSettings();

  const [form, setForm] = useState<Form | null>(null);
  const [errors, setErrors] = useState<Errors>({});

  // Seeded during render so the form never paints a frame empty — the same
  // idiom as CompanyCard beside it.
  const [seededFrom, setSeededFrom] = useState<Settings | null>(null);
  if (settings.data && settings.data !== seededFrom) {
    setSeededFrom(settings.data);
    setForm(pick(settings.data));
  }

  function field(key: LetterheadKey, value: string) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  function validate(current: Form): Errors {
    const found: Errors = {};
    const gstin = current.company_gstin.trim();
    if (gstin && !/^[0-9A-Z]{15}$/.test(gstin)) {
      found.company_gstin = "A GSTIN is 15 letters and digits, like 33AAIFE2328P1Z9.";
    }
    if (current.company_pincode.trim() && !/^\d{6}$/.test(current.company_pincode.trim())) {
      found.company_pincode = "A PIN code is six digits.";
    }
    return found;
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form) return;
    const found = validate(form);
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    const trimmed = Object.fromEntries(
      KEYS.map((k) => [k, form[k].trim()]),
    ) as Form;
    update.mutate(trimmed, {
      onSuccess: () => toast.success("Letterhead saved."),
      onError: (error) => setErrors({ form: errorMessage(error) }),
    });
  }

  if (settings.isPending || !form) {
    return (
      <Card>
        <CardHeader title="Letterhead" />
        <CardBody>
          <Loading />
        </CardBody>
      </Card>
    );
  }

  if (settings.isError) {
    return (
      <ErrorState
        title="Could not load the letterhead"
        error={settings.error}
        onRetry={() => settings.refetch()}
      />
    );
  }

  const text = (key: LetterheadKey, label: string, extra: Partial<{ hint: string }> = {}) => (
    <FormField label={label} error={errors[key]} hint={extra.hint}>
      {(props) => (
        <Input {...props} value={form[key]} onChange={(e) => field(key, e.target.value)} />
      )}
    </FormField>
  );

  return (
    <Card>
      <form onSubmit={onSubmit} noValidate>
        <CardHeader
          title="Letterhead"
          description="Printed at the head and foot of every document the app produces."
        />
        <CardBody className="space-y-5">
          <Section title="Company address" hint="Under the company name at the top of the page.">
            {text("company_address_line1", "Address line 1")}
            {text("company_address_line2", "Address line 2")}
            <div className="grid gap-4 sm:grid-cols-3">
              {text("company_city", "City")}
              {text("company_state", "State")}
              {text("company_pincode", "PIN code")}
            </div>
          </Section>

          <Section title="Registration & contact" hint="In the footer, with the GSTIN.">
            {text("company_gstin", "GSTIN")}
            <div className="grid gap-4 sm:grid-cols-3">
              {text("company_phone", "Phone")}
              {text("company_mobile", "Mobile")}
              {text("company_email", "Email")}
            </div>
          </Section>

          <Section title="Signatory" hint="Whose name closes the letter.">
            <div className="grid gap-4 sm:grid-cols-2">
              {text("signatory_name", "Name")}
              {text("signatory_designation", "Designation", { hint: "Optional." })}
            </div>
          </Section>

          {errors.form ? (
            <p className="text-[13px] text-red" role="alert">
              {errors.form}
            </p>
          ) : null}
        </CardBody>
        <CardFooter>
          <Button type="submit" variant="primary" loading={update.isPending}>
            Save letterhead
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}

function Section({ title, hint, children }: { title: string; hint: string; children: ReactNode }) {
  return (
    <fieldset className="space-y-3">
      <legend className="mb-1">
        <span className={eyebrowCls}>{title}</span>
        <span className="ml-2 text-[12px] text-ink-2">{hint}</span>
      </legend>
      {children}
    </fieldset>
  );
}
