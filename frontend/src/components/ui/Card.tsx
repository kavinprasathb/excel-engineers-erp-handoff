import type { HTMLAttributes, ReactNode } from "react";
import { cardCls } from "./styles";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function Card({ className = "", children, ...rest }: CardProps) {
  return (
    <div className={`${cardCls} ${className}`} {...rest}>
      {children}
    </div>
  );
}

/** Header row for a card that owns its own save button. */
export function CardHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mx-4 flex flex-wrap items-start justify-between gap-3 border-b border-line pb-3.5 pt-4 sm:mx-5 sm:pt-5">
      <div className="min-w-0">
        <h2 className="font-display text-[15.5px] font-extrabold tracking-tight text-heading">{title}</h2>
        {description ? <p className="mt-0.5 text-[13px] text-ink-2">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function CardBody({ className = "", children }: { className?: string; children: ReactNode }) {
  return <div className={`p-4 sm:p-5 ${className}`}>{children}</div>;
}

/** Actions live at the bottom-right on desktop, full-width stacked on a phone. */
export function CardFooter({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2 border-t border-line p-4 sm:flex-row sm:justify-end sm:p-5">
      {children}
    </div>
  );
}
