import type { InputHTMLAttributes } from "react";
import { forwardRef } from "react";
import { inputSizedCls } from "./styles";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

/** forwardRef so FormField can move focus to the first bad field on submit. */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { invalid, className = "", ...rest },
  ref,
) {
  return (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={`${inputSizedCls} ${invalid ? "border-red focus:border-red" : ""} ${className}`}
      {...rest}
    />
  );
});
