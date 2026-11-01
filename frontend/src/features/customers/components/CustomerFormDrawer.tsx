import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { Drawer } from "../../../components/ui/Drawer";
import { Button } from "../../../components/ui/Button";
import { FormField } from "../../../components/ui/FormField";
import { Input } from "../../../components/ui/Input";
import { Textarea } from "../../../components/ui/Textarea";
import { errorCardCls, eyebrowCls } from "../../../components/ui/styles";
import { errorMessage } from "../../../lib/errors";
import { useToast } from "../../../components/ui/toast-context";
import { useCreateCustomer, useUpdateCustomer } from "../api";
import type { Customer, CustomerCreate } from "../../../api/types";
import { BranchesSection } from "../../contacts/BranchesSection";
import { ContactListField } from "../../contacts/ContactListField";
import { cleanContacts, hasContactErrors } from "../../contacts/contactValues";
import { normaliseGstin, partyErrors } from "../../contacts/partyRules";
import type { PartyErrors } from "../../contacts/partyRules";

/** Optional text is "" on the wire, never null — the contract is explicit. */
const BLANK: CustomerCreate = {
  name: "",
  contact_person: "",
  designation: "",
  phone: "",
  email: "",
  emails: [],
  phones: [],
  gstin: "",
  billing_address_line1: "",
  billing_address_line2: "",
  billing_city: "",
  billing_state: "",
  billing_pincode: "",
  shipping_address_line1: "",
  shipping_address_line2: "",
  shipping_city: "",
  shipping_state: "",
  shipping_pincode: "",
  notes: "",
  is_active: true,
};

function toForm(customer: Customer): CustomerCreate {
  // The code, branches and flags are the server's; only the editable fields
  // go back. Shipping state/pincode are not shown, but they stay in the
  // draft so a save sends back the stored values unchanged.
  const { id: _id, code: _code, branches: _branches, missing_fields: _missing, ...rest } = customer;
  return rest;
}

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="space-y-4 border-t border-line pt-4">
      <div>
        <h3 className={eyebrowCls}>{title}</h3>
        {hint ? <p className="mt-1 text-[12px] text-ink-2">{hint}</p> : null}
      </div>
      {children}
    </section>
  );
}

export function CustomerFormDrawer({
  open,
  customer,
  onClose,
  onCreated,
}: {
  open: boolean;
  /** null means "create". */
  customer: Customer | null;
  onClose: () => void;
  /** After a create: the page reopens the drawer on the new record, for its branches. */
  onCreated?: (customer: Customer) => void;
}) {
  const toast = useToast();
  const create = useCreateCustomer();
  const update = useUpdateCustomer();
  const pending = create.isPending || update.isPending;
  const error = create.error ?? update.error;

  const [form, setForm] = useState<CustomerCreate>(BLANK);
  const [nameError, setNameError] = useState<string | undefined>(undefined);
  const [errors, setErrors] = useState<PartyErrors>({});
  const [contactsTouched, setContactsTouched] = useState(false);

  // Reseed whenever the drawer is pointed at a different record, during render
  // so the fields are never briefly the previous customer's.
  const identity = open ? (customer?.id ?? "new") : null;
  const [seeded, setSeeded] = useState<number | "new" | null>(null);
  if (identity !== seeded) {
    setSeeded(identity);
    setForm(customer ? toForm(customer) : BLANK);
    setNameError(undefined);
    setErrors({});
    setContactsTouched(false);
    create.reset();
    update.reset();
  }

  function field<K extends keyof CustomerCreate>(key: K, value: CustomerCreate[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const found = partyErrors({
      gstin: form.gstin,
      city: form.billing_city,
      state: form.billing_state,
      pincode: form.billing_pincode,
    });
    setNameError(form.name.trim() ? undefined : "Enter a customer name.");
    setErrors(found);
    if (!form.name.trim() || Object.keys(found).length > 0) return;
    if (hasContactErrors("email", form.emails) || hasContactErrors("phone", form.phones)) {
      setContactsTouched(true);
      return;
    }
    const emails = cleanContacts("email", form.emails);
    const phones = cleanContacts("phone", form.phones);
    const payload = {
      ...form,
      name: form.name.trim(),
      gstin: normaliseGstin(form.gstin),
      billing_city: form.billing_city.trim(),
      billing_state: form.billing_state.trim(),
      billing_pincode: form.billing_pincode.trim(),
      emails,
      phones,
      email: emails[0] ?? "",
      phone: phones[0] ?? "",
    };

    if (customer) {
      update.mutate(
        { id: customer.id, patch: payload },
        {
          onSuccess: () => {
            toast.success("Customer updated.");
            onClose();
          },
        },
      );
    } else {
      create.mutate(payload, {
        onSuccess: (created) => {
          toast.success(`Customer ${created.code} added. You can add its branches now.`);
          if (onCreated) onCreated(created);
          else onClose();
        },
      });
    }
  }

  const missing = customer?.missing_fields ?? [];

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={customer ? "Edit customer" : "New customer"}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form="customer-form" variant="primary" loading={pending}>
            {customer ? "Save changes" : "Add customer"}
          </Button>
        </>
      }
    >
      <form id="customer-form" onSubmit={onSubmit} noValidate className="space-y-4">
        {missing.length > 0 ? (
          <p className="rounded-md border border-amber/30 bg-amber-bg px-3 py-2 text-[13px] text-ink" role="status">
            This customer was saved before these details were mandatory. Please complete:{" "}
            <b>{missing.join(", ")}</b>.
          </p>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-[1fr_11rem]">
          <FormField label="Company Name" required error={nameError}>
            {(props) => (
              <Input {...props} value={form.name} onChange={(e) => field("name", e.target.value)} />
            )}
          </FormField>
          <FormField label="Customer Code" hint={customer ? "Issued automatically." : "Issued when saved."}>
            {(props) => (
              <Input {...props} readOnly value={customer?.code ?? ""} placeholder="CUST-…" />
            )}
          </FormField>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Contact Person">
            {(props) => (
              <Input
                {...props}
                value={form.contact_person}
                onChange={(e) => field("contact_person", e.target.value)}
              />
            )}
          </FormField>
          <FormField label="Designation">
            {(props) => (
              <Input
                {...props}
                value={form.designation}
                onChange={(e) => field("designation", e.target.value)}
              />
            )}
          </FormField>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <ContactListField
            kind="phone"
            label="Mobile Numbers"
            values={form.phones}
            onChange={(v) => field("phones", v)}
            showErrors={contactsTouched}
          />
          <ContactListField
            kind="email"
            label="Email IDs"
            values={form.emails}
            onChange={(v) => field("emails", v)}
            showErrors={contactsTouched}
          />
        </div>

        <FormField label="GST Number" required error={errors.gstin}>
          {(props) => (
            <Input
              {...props}
              placeholder="33AAIFE2328P1Z9"
              value={form.gstin}
              onChange={(e) => field("gstin", e.target.value.toUpperCase())}
            />
          )}
        </FormField>

        <Section title="Address" hint="Prints in the customer block on every document.">
          <FormField label="Address Line 1">
            {(props) => (
              <Input
                {...props}
                value={form.billing_address_line1}
                onChange={(e) => field("billing_address_line1", e.target.value)}
              />
            )}
          </FormField>
          <FormField label="Address Line 2">
            {(props) => (
              <Input
                {...props}
                value={form.billing_address_line2}
                onChange={(e) => field("billing_address_line2", e.target.value)}
              />
            )}
          </FormField>
          <div className="grid gap-4 sm:grid-cols-3">
            <FormField label="City" required error={errors.city}>
              {(props) => (
                <Input
                  {...props}
                  value={form.billing_city}
                  onChange={(e) => field("billing_city", e.target.value)}
                />
              )}
            </FormField>
            <FormField label="State" required error={errors.state}>
              {(props) => (
                <Input
                  {...props}
                  value={form.billing_state}
                  onChange={(e) => field("billing_state", e.target.value)}
                />
              )}
            </FormField>
            <FormField label="Pin Code" required error={errors.pincode}>
              {(props) => (
                <Input
                  {...props}
                  inputMode="numeric"
                  maxLength={6}
                  value={form.billing_pincode}
                  onChange={(e) => field("billing_pincode", e.target.value)}
                />
              )}
            </FormField>
          </div>
        </Section>

        {/* Stated, not implemented: nothing copies billing into shipping here,
            because the API and the PDF both read blank as "same as billing" and
            a helpful pre-fill would freeze today's billing address into the
            shipping fields the moment billing changes. */}
        <Section
          title="Shipping address"
          hint="Leave these blank if goods ship to the billing address — blank means same as billing, and nothing is copied across."
        >
          <FormField label="Shipping address line 1">
            {(props) => (
              <Input
                {...props}
                value={form.shipping_address_line1}
                onChange={(e) => field("shipping_address_line1", e.target.value)}
              />
            )}
          </FormField>
          <FormField label="Shipping address line 2">
            {(props) => (
              <Input
                {...props}
                value={form.shipping_address_line2}
                onChange={(e) => field("shipping_address_line2", e.target.value)}
              />
            )}
          </FormField>
          <FormField label="Shipping city">
            {(props) => (
              <Input
                {...props}
                value={form.shipping_city}
                onChange={(e) => field("shipping_city", e.target.value)}
              />
            )}
          </FormField>
          <FormField label="Notes">
            {(props) => (
              <Textarea
                {...props}
                value={form.notes}
                onChange={(e) => field("notes", e.target.value)}
              />
            )}
          </FormField>
        </Section>

        {error ? (
          <div className={errorCardCls} role="alert">
            <p className="text-[13px] font-medium text-red">Could not save this customer</p>
            <p className="mt-0.5 text-[13px] text-ink-2">{errorMessage(error)}</p>
          </div>
        ) : null}
      </form>

      <div className="mt-4">
        {customer ? (
          <BranchesSection kind="customers" parentId={customer.id} />
        ) : (
          <section className="border-t border-line pt-4">
            <h3 className={eyebrowCls}>Branches</h3>
            <p className="mt-1 text-[12px] text-ink-2">
              Optional. Add the customer first; its branches can be added right after.
            </p>
          </section>
        )}
      </div>
    </Drawer>
  );
}
