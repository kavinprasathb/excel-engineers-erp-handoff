import { useState } from "react";
import type { FormEvent } from "react";
import { Drawer } from "../../../components/ui/Drawer";
import { Button } from "../../../components/ui/Button";
import { FormField } from "../../../components/ui/FormField";
import { Input } from "../../../components/ui/Input";
import { Textarea } from "../../../components/ui/Textarea";
import { errorCardCls, eyebrowCls } from "../../../components/ui/styles";
import { errorMessage } from "../../../lib/errors";
import { useToast } from "../../../components/ui/toast-context";
import { useCreateSupplier, useUpdateSupplier } from "../api";
import type { SupplierInput } from "../api";
import type { Supplier } from "../../../api/types";
import { BranchesSection } from "../../contacts/BranchesSection";
import { ContactListField } from "../../contacts/ContactListField";
import { cleanContacts, hasContactErrors } from "../../contacts/contactValues";
import { normaliseGstin, partyErrors } from "../../contacts/partyRules";
import type { PartyErrors } from "../../contacts/partyRules";

/** Optional text is "" on the wire, never null — the contract is explicit. */
const BLANK: SupplierInput = {
  name: "",
  contact_person: "",
  phone: "",
  email: "",
  emails: [],
  phones: [],
  gstin: "",
  address_line1: "",
  address_line2: "",
  city: "",
  state: "",
  pincode: "",
  notes: "",
  is_active: true,
};

function toForm(supplier: Supplier): SupplierInput {
  const {
    id: _id,
    code: _code,
    product_count: _count,
    branches: _branches,
    missing_fields: _missing,
    ...rest
  } = supplier;
  return rest;
}

export function SupplierFormDrawer({
  open,
  supplier,
  onClose,
  onCreated,
}: {
  open: boolean;
  /** null means "create". */
  supplier: Supplier | null;
  onClose: () => void;
  /** After a create: the page reopens the drawer on the new record, for its branches. */
  onCreated?: (supplier: Supplier) => void;
}) {
  const toast = useToast();
  const create = useCreateSupplier();
  const update = useUpdateSupplier();
  const pending = create.isPending || update.isPending;
  const error = create.error ?? update.error;

  const [form, setForm] = useState<SupplierInput>(BLANK);
  const [nameError, setNameError] = useState<string | undefined>(undefined);
  const [errors, setErrors] = useState<PartyErrors>({});
  const [contactsTouched, setContactsTouched] = useState(false);

  // Reseed whenever the drawer is pointed at a different record, during render
  // so the fields are never briefly the previous supplier's.
  const identity = open ? (supplier?.id ?? "new") : null;
  const [seeded, setSeeded] = useState<number | "new" | null>(null);
  if (identity !== seeded) {
    setSeeded(identity);
    setForm(supplier ? toForm(supplier) : BLANK);
    setNameError(undefined);
    setErrors({});
    setContactsTouched(false);
    create.reset();
    update.reset();
  }

  function field<K extends keyof SupplierInput>(key: K, value: SupplierInput[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const found = partyErrors(form);
    setNameError(form.name.trim() ? undefined : "Enter a supplier name.");
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
      city: form.city.trim(),
      state: form.state.trim(),
      pincode: form.pincode.trim(),
      emails,
      phones,
      email: emails[0] ?? "",
      phone: phones[0] ?? "",
    };

    if (supplier) {
      update.mutate(
        { id: supplier.id, patch: payload },
        {
          onSuccess: () => {
            toast.success("Supplier updated.");
            onClose();
          },
        },
      );
    } else {
      create.mutate(payload, {
        onSuccess: (created) => {
          toast.success(`Supplier ${created.code} added. You can add its branches now.`);
          if (onCreated) onCreated(created);
          else onClose();
        },
      });
    }
  }

  const missing = supplier?.missing_fields ?? [];

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={supplier ? "Edit supplier" : "New supplier"}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form="supplier-form" variant="primary" loading={pending}>
            {supplier ? "Save changes" : "Add supplier"}
          </Button>
        </>
      }
    >
      <form id="supplier-form" onSubmit={onSubmit} noValidate className="space-y-4">
        {missing.length > 0 ? (
          <p className="rounded-md border border-amber/30 bg-amber-bg px-3 py-2 text-[13px] text-ink" role="status">
            This supplier was saved before these details were mandatory. Please complete:{" "}
            <b>{missing.join(", ")}</b>.
          </p>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-[1fr_11rem]">
          <FormField label="Supplier Name" required error={nameError}>
            {(props) => (
              <Input
                {...props}
                value={form.name}
                onChange={(e) => field("name", e.target.value)}
              />
            )}
          </FormField>
          <FormField label="Supplier Code" hint={supplier ? "Issued automatically." : "Issued when saved."}>
            {(props) => (
              <Input {...props} readOnly value={supplier?.code ?? ""} placeholder="SUP-…" />
            )}
          </FormField>
        </div>

        <FormField label="Contact person">
          {(props) => (
            <Input
              {...props}
              value={form.contact_person}
              onChange={(e) => field("contact_person", e.target.value)}
            />
          )}
        </FormField>

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

        <FormField label="Address Line 1">
          {(props) => (
            <Input
              {...props}
              value={form.address_line1}
              onChange={(e) => field("address_line1", e.target.value)}
            />
          )}
        </FormField>

        <FormField label="Address Line 2">
          {(props) => (
            <Input
              {...props}
              value={form.address_line2}
              onChange={(e) => field("address_line2", e.target.value)}
            />
          )}
        </FormField>

        <div className="grid gap-4 sm:grid-cols-3">
          <FormField label="City" required error={errors.city}>
            {(props) => (
              <Input
                {...props}
                value={form.city}
                onChange={(e) => field("city", e.target.value)}
              />
            )}
          </FormField>
          <FormField label="State" required error={errors.state}>
            {(props) => (
              <Input
                {...props}
                value={form.state}
                onChange={(e) => field("state", e.target.value)}
              />
            )}
          </FormField>
          <FormField label="Pin Code" required error={errors.pincode}>
            {(props) => (
              <Input
                {...props}
                inputMode="numeric"
                maxLength={6}
                value={form.pincode}
                onChange={(e) => field("pincode", e.target.value)}
              />
            )}
          </FormField>
        </div>

        <FormField label="Notes">
          {(props) => (
            <Textarea
              {...props}
              value={form.notes}
              onChange={(e) => field("notes", e.target.value)}
            />
          )}
        </FormField>

        {error ? (
          <div className={errorCardCls} role="alert">
            <p className="text-[13px] font-medium text-red">Could not save this supplier</p>
            <p className="mt-0.5 text-[13px] text-ink-2">{errorMessage(error)}</p>
          </div>
        ) : null}
      </form>

      <div className="mt-4">
        {supplier ? (
          <BranchesSection kind="suppliers" parentId={supplier.id} />
        ) : (
          <section className="border-t border-line pt-4">
            <h3 className={eyebrowCls}>Branches</h3>
            <p className="mt-1 text-[12px] text-ink-2">
              Optional. Add the supplier first; its branches can be added right after.
            </p>
          </section>
        )}
      </div>
    </Drawer>
  );
}
