import { useState } from "react";
import type { FormEvent } from "react";
import { Card, CardBody, CardFooter, CardHeader } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { FormField } from "../../components/ui/FormField";
import { Input } from "../../components/ui/Input";
import { useToast } from "../../components/ui/toast-context";
import { errorMessage } from "../../lib/errors";
import { isApiError } from "../../api/client";
import { useChangePassword } from "../auth/api";

const MIN_LENGTH = 8;

interface Errors {
  current?: string;
  next?: string;
  confirm?: string;
}

export function PasswordCard() {
  const toast = useToast();
  const changePassword = useChangePassword();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<Errors>({});

  function validate(): Errors {
    const e: Errors = {};
    if (!current) e.current = "Enter your current password.";
    if (next.length < MIN_LENGTH) e.next = `Use at least ${MIN_LENGTH} characters.`;
    else if (next === current) e.next = "The new password must be different.";
    if (confirm !== next) e.confirm = "The two passwords do not match.";
    return e;
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    changePassword.mutate(
      { current_password: current, new_password: next },
      {
        onSuccess: () => {
          setCurrent("");
          setNext("");
          setConfirm("");
          setErrors({});
          toast.success("Password changed.");
        },
        onError: (error) => {
          // The server rotates the session on success; on failure the only
          // thing it can reasonably reject is the current password.
          if (isApiError(error) && error.status === 401) {
            setErrors({ current: "That is not your current password." });
            return;
          }
          setErrors({ current: errorMessage(error) });
        },
      },
    );
  }

  return (
    <Card>
      <form onSubmit={onSubmit} noValidate>
        <CardHeader
          title="Change password"
          description="You stay signed in on this device; other devices are signed out."
        />
        <CardBody className="space-y-4">
          {/* Hidden username field so password managers file the update
              against the right account. */}
          <input type="text" name="username" autoComplete="username" hidden readOnly value="" />

          <FormField label="Current password" required error={errors.current}>
            {(props) => (
              <Input
                {...props}
                type="password"
                autoComplete="current-password"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
              />
            )}
          </FormField>

          <FormField
            label="New password"
            required
            error={errors.next}
            hint={`At least ${MIN_LENGTH} characters.`}
          >
            {(props) => (
              <Input
                {...props}
                type="password"
                autoComplete="new-password"
                value={next}
                onChange={(e) => setNext(e.target.value)}
              />
            )}
          </FormField>

          <FormField label="Confirm new password" required error={errors.confirm}>
            {(props) => (
              <Input
                {...props}
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            )}
          </FormField>
        </CardBody>
        <CardFooter>
          <Button type="submit" variant="primary" loading={changePassword.isPending}>
            Change password
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
