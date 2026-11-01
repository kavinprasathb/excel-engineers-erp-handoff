import type { ReactNode } from "react";
import { useId } from "react";
import { createPortal } from "react-dom";
import { useBodyScrollLock, useEscapeKey, useFocusTrap } from "../../lib/overlay";
import { modalBackdropCls, modalPanelCls } from "./styles";
import { Icon } from "./Icon";

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  /** Buttons, laid out full-width stacked on a phone. */
  footer?: ReactNode;
  /** A wider panel from `sm` up, for tables. */
  wide?: boolean;
}

export function Modal({ open, onClose, title, description, children, footer, wide }: ModalProps) {
  const titleId = useId();
  const descId = useId();
  const panelRef = useFocusTrap(open);

  useBodyScrollLock(open);
  useEscapeKey(open, onClose);

  if (!open) return null;

  return createPortal(
    <div
      className={modalBackdropCls}
      // Only a click that both starts and ends on the backdrop closes, so a
      // drag that began inside the panel does not dismiss it.
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        className={wide ? modalPanelCls.replace("sm:max-w-lg", "sm:max-w-6xl") : modalPanelCls}
      >
        <div className="flex items-start justify-between gap-3 border-b border-line p-4 sm:p-5">
          <div className="min-w-0">
            <h2 id={titleId} className="text-[15px] font-semibold tracking-tight text-ink">
              {title}
            </h2>
            {description ? (
              <p id={descId} className="mt-0.5 text-[13px] text-ink-2">
                {description}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="-mr-1 -mt-1 flex h-11 w-11 items-center justify-center rounded-lg border border-transparent text-ink-2 transition-colors hover:bg-hoverfill hover:text-ink md:h-8 md:w-8"
          >
            <Icon name="close" />
          </button>
        </div>

        <div className="max-h-[70vh] overflow-y-auto p-4 sm:p-5">{children}</div>

        {footer ? (
          <div className="flex flex-col gap-2 border-t border-line p-4 sm:flex-row sm:justify-end sm:p-5">
            {footer}
          </div>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}
