import type { ReactNode } from "react";
import { gutterCls, pageHeadingCls } from "../ui/styles";

export interface PageHeaderProps {
  title: string;
  description?: string;
  /** One primary action at most; everything else is a ghost button. */
  actions?: ReactNode;
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <header className={`pt-5 pb-1 sm:pt-7 ${gutterCls}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className={pageHeadingCls}>{title}</h1>
          {description ? <p className="mt-1 text-[13.5px] text-ink-2">{description}</p> : null}
        </div>
        {/* Actions stack full-width on a phone so they clear 44px comfortably. */}
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
    </header>
  );
}

/** The standard content well. Pages render into this, never into raw <main>. */
export function PageBody({ children }: { children: ReactNode }) {
  return <div className={`py-4 sm:py-6 ${gutterCls}`}>{children}</div>;
}
