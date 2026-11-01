import type { TextareaHTMLAttributes } from "react";
import { forwardRef } from "react";
import { textareaCls } from "./styles";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { invalid, className = "", rows = 3, ...rest },
  ref,
) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      aria-invalid={invalid || undefined}
      className={`${textareaCls} ${invalid ? "border-red focus:border-red" : ""} ${className}`}
      {...rest}
    />
  );
});
