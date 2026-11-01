import type { ReactNode } from "react";
import { useId } from "react";
import { Label } from "./Label";
import { fieldErrorCls } from "./styles";

export interface FormFieldProps {
  label: string;
  required?: boolean;
  /** Shown below the control; suppressed while `error` is present. */
  hint?: string;
  error?: string;
  /**
   * Receives the wiring the control needs. Rendering as a function keeps the
   * id/aria plumbing in one place instead of at every call site.
   */
  children: (props: {
    id: string;
    "aria-describedby": string | undefined;
    invalid: boolean;
  }) => ReactNode;
}

export function FormField({ label, required, hint, error, children }: FormFieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const describedBy = error ? errorId : hint ? hintId : undefined;

  return (
    <div>
      <Label htmlFor={id} required={required}>
        {label}
      </Label>
      {children({ id, "aria-describedby": describedBy, invalid: Boolean(error) })}
      {error ? (
        // role=alert so the message is announced the moment validation fails.
        <p id={errorId} role="alert" className={fieldErrorCls}>
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="mt-1.5 text-[12px] text-ink-2">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
