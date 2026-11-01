import type { LabelHTMLAttributes, ReactNode } from "react";
import { labelCls } from "./styles";

export interface LabelProps extends LabelHTMLAttributes<HTMLLabelElement> {
  /** Marks the field visually and for assistive tech. */
  required?: boolean;
  children: ReactNode;
}

export function Label({ required, className = "", children, ...rest }: LabelProps) {
  return (
    <label className={`${labelCls} ${className}`} {...rest}>
      {children}
      {required ? (
        <span className="ml-0.5 text-red" aria-hidden="true">
          *
        </span>
      ) : null}
    </label>
  );
}
