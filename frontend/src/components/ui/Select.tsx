import type { SelectHTMLAttributes } from "react";
import { forwardRef } from "react";
import { selectCls } from "./styles";
import { Icon } from "./Icon";

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  invalid?: boolean;
}

/**
 * A native <select> — a phone gets its own picker, which beats anything we
 * could hand-roll. `appearance-none` plus our own chevron only so the control
 * matches the inputs beside it.
 */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { invalid, className = "", children, ...rest },
  ref,
) {
  return (
    <div className="relative">
      <select
        ref={ref}
        aria-invalid={invalid || undefined}
        className={`${selectCls} ${invalid ? "border-red focus:border-red" : ""} ${className}`}
        {...rest}
      >
        {children}
      </select>
      <Icon
        name="chevronDown"
        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-2"
      />
    </div>
  );
});
