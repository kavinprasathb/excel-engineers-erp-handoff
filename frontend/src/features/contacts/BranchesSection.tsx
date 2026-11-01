import { useState } from "react";
import type { FormEvent } from "react";
import { Button } from "../../components/ui/Button";
import { FormField } from "../../components/ui/FormField";
import { Input } from "../../components/ui/Input";
import { Icon } from "../../components/ui/Icon";
import { errorCardCls, eyebrowCls } from "../../components/ui/styles";
import { errorMessage } from "../../lib/errors";
import { useToast } from "../../components/ui/toast-context";
import { useIsOwner } from "../auth/api";
import type { CustomerBranch, CustomerBranchInput, SupplierBranch } from "../../api/types";
import { ContactListField } from "./ContactListField";
import { cleanContacts, hasContactErrors } from "./contactValues";
import { useBranchMutations, useParty } from "./branchApi";
import type { PartyKind } from "./branchApi";
import { formatAddress, normaliseGstin, partyErrors } from "./partyRules";
import type { PartyErrors } from "./partyRules";

/** Every field a branch can carry; supplier branches leave out the contact person. */
type BranchForm = CustomerBranchInput;

const BLANK: BranchForm = {
  name: "",
  gstin: "",
  contact_person: "",
  designation: "",
  emails: [],
  phones: [],
  address_line1: "",
  city: "",
  state: "",
  pincode: "",
};

function toForm(b: SupplierBranch | CustomerBranch): BranchForm {
  return {
    name: b.name,
    gstin: b.gstin,
    contact_person: "contact_person" in b ? b.contact_person : "",
    designation: "designation" in b ? b.designation : "",
    emails: b.emails,
    phones: b.phones,
    address_line1: b.address_line1,
    city: b.city,
    state: b.state,
    pincode: b.pincode,
  };
}

/**
 * The optional branches of one customer or supplier: zero, one or many, each
 * with its own code (issued by the server), GST number and address. Lives
 * outside the parent's own form, and saves each branch on its own.
 */
export function BranchesSection({ kind, parentId }: { kind: PartyKind; parentId: number }) {
  const toast = useToast();
  const owner = useIsOwner();
  const party = useParty(kind, parentId);
  const { create, update, remove } = useBranchMutations(kind, parentId);
  const contacts = kind === "customers";
  // null: no editor open; "new": adding; a number: editing that branch.
  const [editing, setEditing] = useState<"new" | number | null>(null);
  const [form, setForm] = useState<BranchForm>(BLANK);
  const [errors, setErrors] = useState<PartyErrors & { name?: string }>({});
  const [contactsTouched, setContactsTouched] = useState(false);

  const branches = (party.data?.branches ?? []).filter((b) => b.is_active);
  const saving = create.isPending || update.isPending;
  const saveError = create.error ?? update.error;

  function open(target: "new" | SupplierBranch | CustomerBranch) {
    setEditing(target === "new" ? "new" : target.id);
    setForm(target === "new" ? BLANK : toForm(target));
    setErrors({});
    setContactsTouched(false);
    create.reset();
    update.reset();
  }

  function field<K extends keyof BranchForm>(key: K, value: BranchForm[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // The parent drawer's form must not see this submit.
    event.stopPropagation();
    const found: PartyErrors & { name?: string } = partyErrors(form);
    if (!form.name.trim()) found.name = "Enter the branch name.";
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    if (hasContactErrors("email", form.emails) || hasContactErrors("phone", form.phones)) {
      setContactsTouched(true);
      return;
    }
    const base = {
      name: form.name.trim(),
      gstin: normaliseGstin(form.gstin),
      emails: cleanContacts("email", form.emails),
      phones: cleanContacts("phone", form.phones),
      address_line1: form.address_line1.trim(),
      city: form.city.trim(),
      state: form.state.trim(),
      pincode: form.pincode.trim(),
    };
    const body = contacts
      ? { ...base, contact_person: form.contact_person.trim(), designation: form.designation.trim() }
      : base;
    const done = {
      onSuccess: () => {
        toast.success(editing === "new" ? "Branch added." : "Branch updated.");
        setEditing(null);
      },
    };
    if (editing === "new") create.mutate(body as CustomerBranchInput, done);
    else if (editing !== null) update.mutate({ id: editing, patch: body as CustomerBranchInput }, done);
  }

  function onRemove(b: SupplierBranch) {
    remove.mutate(b.id, {
      onSuccess: () => toast.success(`${b.name} removed.`),
      onError: (e) => toast.error(errorMessage(e)),
    });
  }

  return (
    <section className="space-y-3 border-t border-line pt-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className={eyebrowCls}>Branches</h3>
          <p className="mt-1 text-[12px] text-ink-2">
            Optional. A {kind === "customers" ? "quotation" : "purchase order"} addressed to a branch
            prints the branch&apos;s GST number and address.
          </p>
        </div>
        {editing === null ? (
          <Button size="sm" onClick={() => open("new")}>
            <Icon name="plus" size={14} />
            Add Branch
          </Button>
        ) : null}
      </div>

      {branches.length === 0 && editing !== "new" ? (
        <p className="text-[13px] text-ink-2">No branches.</p>
      ) : (
        <ul className="space-y-2">
          {branches.map((b) =>
            editing === b.id ? null : (
              <li key={b.id} className="rounded-md border border-line p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-medium text-ink">{b.name}</p>
                    <p className="text-[12px] text-ink-2 tabular-nums">
                      {b.code} · GST {b.gstin}
                    </p>
                    <p className="truncate text-[12px] text-ink-2">
                      {formatAddress(b.address_line1, b.city, b.state, b.pincode)}
                    </p>
                  </div>
                  {editing === null ? (
                    <div className="flex shrink-0 gap-2">
                      <Button size="sm" onClick={() => open(b)}>
                        Edit
                      </Button>
                      {owner ? (
                        <Button size="sm" loading={remove.isPending && remove.variables === b.id} onClick={() => onRemove(b)}>
                          Remove
                        </Button>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </li>
            ),
          )}
        </ul>
      )}

      {editing !== null ? (
        <form onSubmit={onSubmit} noValidate className="space-y-4 rounded-md border border-line bg-hoverfill p-3">
          <p className="text-[13px] font-medium text-ink">
            {editing === "new" ? "New branch" : `Edit ${branches.find((b) => b.id === editing)?.code ?? "branch"}`}
          </p>
          <FormField label="Branch Name" required error={errors.name}>
            {(p) => <Input {...p} value={form.name} onChange={(e) => field("name", e.target.value)} />}
          </FormField>
          <FormField label="GST Number" required error={errors.gstin}>
            {(p) => (
              <Input
                {...p}
                placeholder="33AAIFE2328P1Z9"
                value={form.gstin}
                onChange={(e) => field("gstin", e.target.value.toUpperCase())}
              />
            )}
          </FormField>
          {contacts ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Contact Person">
                {(p) => (
                  <Input {...p} value={form.contact_person} onChange={(e) => field("contact_person", e.target.value)} />
                )}
              </FormField>
              <FormField label="Designation">
                {(p) => (
                  <Input {...p} value={form.designation} onChange={(e) => field("designation", e.target.value)} />
                )}
              </FormField>
            </div>
          ) : null}
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
          <FormField label="Address Line 1">
            {(p) => (
              <Input {...p} value={form.address_line1} onChange={(e) => field("address_line1", e.target.value)} />
            )}
          </FormField>
          <div className="grid gap-4 sm:grid-cols-3">
            <FormField label="City" required error={errors.city}>
              {(p) => <Input {...p} value={form.city} onChange={(e) => field("city", e.target.value)} />}
            </FormField>
            <FormField label="State" required error={errors.state}>
              {(p) => <Input {...p} value={form.state} onChange={(e) => field("state", e.target.value)} />}
            </FormField>
            <FormField label="Pin Code" required error={errors.pincode}>
              {(p) => (
                <Input
                  {...p}
                  inputMode="numeric"
                  maxLength={6}
                  value={form.pincode}
                  onChange={(e) => field("pincode", e.target.value)}
                />
              )}
            </FormField>
          </div>
          {saveError ? (
            <div className={errorCardCls} role="alert">
              <p className="text-[13px] font-medium text-red">Could not save this branch</p>
              <p className="mt-0.5 text-[13px] text-ink-2">{errorMessage(saveError)}</p>
            </div>
          ) : null}
          <div className="flex justify-end gap-2">
            <Button onClick={() => setEditing(null)}>Cancel</Button>
            <Button type="submit" variant="primary" loading={saving}>
              {editing === "new" ? "Add branch" : "Save branch"}
            </Button>
          </div>
        </form>
      ) : null}
    </section>
  );
}
