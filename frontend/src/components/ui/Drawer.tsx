import type { ReactNode } from "react";
import { useId } from "react";
import { createPortal } from "react-dom";
import { useBodyScrollLock, useEscapeKey, useFocusTrap } from "../../lib/overlay";
import { drawerPanelCls } from "./styles";
import { Icon } from "./Icon";

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  /** Anchors the panel to the left edge on desktop; used by the mobile nav. */
  side?: "right" | "left";
}

/**
 * A right rail on desktop, a bottom sheet on a phone — the same component,
 * because the content is identical and only the edge it is attached to changes.
 */
export function Drawer({ open, onClose, title, children, footer, side = "right" }: DrawerProps) {
  const titleId = useId();
  const panelRef = useFocusTrap(open);

  useBodyScrollLock(open);
  useEscapeKey(open, onClose);

  if (!open) return null;

  const sideCls =
    side === "left" ? "md:left-0 md:right-auto md:border-r md:border-l-0" : "";

  return createPortal(
    <>
      <div
        className="fixed inset-0 z-40 bg-black/40"
        onMouseDown={onClose}
        aria-hidden="true"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={`${drawerPanelCls} ${sideCls} flex flex-col`}
      >
        <div className="flex items-center justify-between gap-3 border-b border-line p-4">
          <h2 id={titleId} className="text-[15px] font-semibold tracking-tight text-ink">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="-mr-1 flex h-11 w-11 items-center justify-center rounded-lg border border-transparent text-ink-2 transition-colors hover:bg-hoverfill hover:text-ink md:h-8 md:w-8"
          >
            <Icon name="close" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">{children}</div>

        {footer ? (
          <div className="flex flex-col gap-2 border-t border-line p-4 sm:flex-row sm:justify-end">
            {footer}
          </div>
        ) : null}
      </div>
    </>,
    document.body,
  );
}
