import type { ButtonHTMLAttributes, ReactNode } from "react";
import { btnBaseCls, btnSizeCls, btnVariantCls } from "./styles";
import { Spinner } from "./Spinner";

export type ButtonVariant = keyof typeof btnVariantCls;
export type ButtonSize = keyof typeof btnSizeCls;

export interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type"> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Disables the button and swaps the leading slot for a spinner. */
  loading?: boolean;
  /** Explicit, because a bare <button> inside a form defaults to submit. */
  type?: "button" | "submit" | "reset";
  fullWidth?: boolean;
  children?: ReactNode;
}

export function Button({
  variant = "ghost",
  size = "md",
  loading = false,
  type = "button",
  fullWidth = false,
  disabled,
  className = "",
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`${btnBaseCls} ${btnSizeCls[size]} ${btnVariantCls[variant]} ${
        fullWidth ? "w-full" : ""
      } ${className}`}
      {...rest}
    >
      {loading ? <Spinner /> : null}
      {children}
    </button>
  );
}
