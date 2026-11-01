import { useState } from "react";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { Card, CardBody } from "../../components/ui/Card";
import { FormField } from "../../components/ui/FormField";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { Modal } from "../../components/ui/Modal";
import { Loading } from "../../components/ui/Spinner";
import { ErrorState } from "../../components/ui/ErrorState";
import { Icon } from "../../components/ui/Icon";
import { useToast } from "../../components/ui/toast-context";
import { errorMessage } from "../../lib/errors";
import { OwnerOnly } from "../auth/OwnerOnly";
import { useMe } from "../auth/api";
import { formatQuoteDate } from "../quotations/format";
import { ROLE_LABEL, useCreateStaff, useResetStaffPassword, useStaff, useUpdateStaff } from "./api";
import type { StaffUser } from "./api";
import type { Role } from "../../api/types";

const MIN_PASSWORD = 12;

export default function StaffPage() {
  return (
    <OwnerOnly title="Staff">
      <Staff />
    </OwnerOnly>
  );
}

function Staff() {
  const staff = useStaff();
  const me = useMe();
  const toast = useToast();
  const update = useUpdateStaff();
  const [adding, setAdding] = useState(false);
  const [resetFor, setResetFor] = useState<StaffUser | null>(null);

  return (
    <>
      <PageHeader
        title="Staff"
        description="Who can sign in. Staff do the daily work; only the owner can delete, see purchase cost, analytics, settings and this page."
        actions={
          <Button variant="primary" onClick={() => setAdding(true)}>
            <Icon name="plus" size={15} />
            Add staff
          </Button>
        }
      />
      <PageBody>
        {staff.isPending ? (
          <Loading />
        ) : staff.isError ? (
          <ErrorState title="Could not load staff" error={staff.error} onRetry={() => staff.refetch()} />
        ) : (
          <Card>
            <CardBody>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-[13px]">
                  <thead className="text-left text-[11px] font-medium uppercase tracking-wide text-ink-2">
                    <tr className="border-b border-line">
                      <th className="py-2 pr-3">Name</th>
                      <th className="px-3 py-2">Role</th>
                      <th className="px-3 py-2">Last sign-in</th>
                      <th className="px-3 py-2">Status</th>
                      <th className="py-2 pl-3" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {staff.data.map((u) => {
                      const self = u.id === me.data?.id;
                      return (
                        <tr key={u.id}>
                          <td className="py-2 pr-3">
                            <p className="font-medium text-ink">
                              {u.full_name || "—"} {self ? <span className="text-ink-2">(you)</span> : null}
                            </p>
                            <p className="text-[12px] text-ink-2">{u.email}</p>
                          </td>
                          <td className="px-3 py-2">
                            <Select
                              aria-label={`Role of ${u.full_name}`}
                              value={u.role}
                              disabled={self}
                              onChange={(e) =>
                                update.mutate(
                                  { id: u.id, role: e.target.value as Role },
                                  {
                                    onSuccess: (r) => toast.success(`${r.full_name} is now ${ROLE_LABEL[r.role]}.`),
                                    onError: (err) => toast.error(errorMessage(err)),
                                  },
                                )
                              }
                            >
                              <option value="staff">Staff</option>
                              <option value="admin">Owner</option>
                            </Select>
                          </td>
                          <td className="px-3 py-2 text-ink-2">
                            {u.last_login_at ? formatQuoteDate(u.last_login_at.slice(0, 10)) : "Never"}
                          </td>
                          <td className="px-3 py-2">
                            <Badge tone={u.is_active ? "green" : "gray"}>{u.is_active ? "Active" : "Blocked"}</Badge>
                          </td>
                          <td className="py-2 pl-3">
                            <div className="flex justify-end gap-1">
                              <Button size="sm" onClick={() => setResetFor(u)}>
                                Reset password
                              </Button>
                              {self ? null : (
                                <Button
                                  size="sm"
                                  variant={u.is_active ? "danger" : "ghost"}
                                  onClick={() =>
                                    update.mutate(
                                      { id: u.id, is_active: !u.is_active },
                                      {
                                        onSuccess: (r) =>
                                          toast.success(
                                            r.is_active ? `${r.full_name} can sign in again.` : `${r.full_name} is blocked and signed out.`,
                                          ),
                                        onError: (err) => toast.error(errorMessage(err)),
                                      },
                                    )
                                  }
                                >
                                  {u.is_active ? "Block" : "Unblock"}
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardBody>
          </Card>
        )}
      </PageBody>
      <AddStaff open={adding} onClose={() => setAdding(false)} />
      <ResetPassword user={resetFor} onClose={() => setResetFor(null)} />
    </>
  );
}

function AddStaff({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useCreateStaff();
  const toast = useToast();
  const [form, setForm] = useState({ full_name: "", email: "", role: "staff" as Role, password: "" });
  const [error, setError] = useState<string | null>(null);

  function submit() {
    if (!form.full_name.trim() || !form.email.trim()) return setError("Enter the name and email.");
    if (form.password.length < MIN_PASSWORD) return setError(`The password needs at least ${MIN_PASSWORD} characters.`);
    create.mutate(form, {
      onSuccess: (u) => {
        toast.success(`${u.full_name} can now sign in.`);
        setForm({ full_name: "", email: "", role: "staff", password: "" });
        setError(null);
        onClose();
      },
      onError: (e) => setError(errorMessage(e)),
    });
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add staff"
      description="They sign in with this email and password. Give them the password in person."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={create.isPending} onClick={submit}>
            Add
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <FormField label="Name" required>
          {(p) => <Input {...p} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />}
        </FormField>
        <FormField label="Email" required>
          {(p) => <Input {...p} type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />}
        </FormField>
        <FormField label="Role">
          {(p) => (
            <Select {...p} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
              <option value="staff">Staff</option>
              <option value="admin">Owner</option>
            </Select>
          )}
        </FormField>
        <FormField label="Password" required hint={`At least ${MIN_PASSWORD} characters.`}>
          {(p) => (
            <Input {...p} type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          )}
        </FormField>
        {error ? <p className="text-[13px] text-red">{error}</p> : null}
      </div>
    </Modal>
  );
}

function ResetPassword({ user, onClose }: { user: StaffUser | null; onClose: () => void }) {
  const reset = useResetStaffPassword();
  const toast = useToast();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  function submit() {
    if (!user) return;
    if (password.length < MIN_PASSWORD) return setError(`At least ${MIN_PASSWORD} characters.`);
    reset.mutate(
      { id: user.id, password },
      {
        onSuccess: () => {
          toast.success(`Password changed. ${user.full_name} is signed out everywhere.`);
          setPassword("");
          setError(null);
          onClose();
        },
        onError: (e) => setError(errorMessage(e)),
      },
    );
  }

  return (
    <Modal
      open={user !== null}
      onClose={onClose}
      title={`New password for ${user?.full_name ?? ""}`}
      description="They are signed out on every device and use the new password next time."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={reset.isPending} onClick={submit}>
            Change password
          </Button>
        </>
      }
    >
      <FormField label="New password" required hint={`At least ${MIN_PASSWORD} characters.`}>
        {(p) => <Input {...p} type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
      </FormField>
      {error ? <p className="mt-2 text-[13px] text-red">{error}</p> : null}
    </Modal>
  );
}
