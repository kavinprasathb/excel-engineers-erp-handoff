import type { ReactNode } from "react";
import { Icon } from "./Icon";
import { Art } from "../illustrations/Art";
import { ICON_ART } from "../illustrations/art-map";
import type { IconName } from "./Icon";

/**
 * Empty is not error and not loading. The message should name the filter that
 * produced the emptiness — "no products match this filter" — so the user knows
 * whether to clear something or to add something.
 */
export function EmptyState({
  title,
  description,
  icon = "inbox",
  action,
}: {
  title: string;
  description?: string;
  icon?: IconName;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      {ICON_ART[icon] ? (
        <Art name={ICON_ART[icon]} size={92} />
      ) : (
        <Icon name={icon} size={22} className="text-ink-2/70" />
      )}
      <p className="mt-2 text-[14px] font-medium text-ink">{title}</p>
      {description ? (
        <p className="mt-1 max-w-sm text-[13px] text-ink-2">{description}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
