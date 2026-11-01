import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { ToastApi, ToastItem, ToastTone } from "./toast-context";
import { ToastContext, registerToastSink } from "./toast-context";
import { Icon } from "./Icon";

const DISMISS_MS = 5000;

const TONE_ICON = {
  default: { name: "info", cls: "text-darkbtn-text/70" },
  success: { name: "check", cls: "text-green" },
  error: { name: "alert", cls: "text-red" },
} as const;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const show = useCallback((message: string, tone: ToastTone = "default") => {
    const id = nextId.current++;
    // Three is the point past which the stack covers the content it is
    // reporting on; the oldest drops off.
    setItems((prev) => [...prev.slice(-2), { id, message, tone }]);
    window.setTimeout(() => {
      setItems((prev) => prev.filter((t) => t.id !== id));
    }, DISMISS_MS);
  }, []);

  const api = useMemo<ToastApi>(
    () => ({
      show,
      success: (m: string) => show(m, "success"),
      error: (m: string) => show(m, "error"),
      dismiss,
    }),
    [show, dismiss],
  );

  useEffect(() => {
    registerToastSink(show);
    return () => registerToastSink(null);
  }, [show]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <ToastViewport items={items} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

function ToastViewport({
  items,
  onDismiss,
}: {
  items: ToastItem[];
  onDismiss: (id: number) => void;
}) {
  if (typeof document === "undefined" || items.length === 0) return null;

  return createPortal(
    <div
      // Errors are assertive so they interrupt; the container is polite and
      // each item raises its own urgency.
      aria-live="polite"
      className="pointer-events-none fixed inset-x-4 bottom-4 z-[60] flex flex-col items-stretch gap-2 sm:inset-x-auto sm:bottom-6 sm:right-6 sm:items-end"
    >
      {items.map((t) => {
        const tone = TONE_ICON[t.tone];
        return (
          <div
            key={t.id}
            role={t.tone === "error" ? "alert" : "status"}
            className="pointer-events-auto flex max-w-full items-start gap-2 rounded-xl bg-darkbtn px-4 py-2.5 text-[13px] font-medium text-darkbtn-text shadow-lg sm:max-w-sm sm:rounded-full"
          >
            <Icon name={tone.name} className={`mt-0.5 ${tone.cls}`} />
            <span className="min-w-0 flex-1">{t.message}</span>
            <button
              type="button"
              onClick={() => onDismiss(t.id)}
              aria-label="Dismiss"
              className="-mr-1 shrink-0 text-darkbtn-text/60 transition-colors hover:text-darkbtn-text"
            >
              <Icon name="close" size={15} />
            </button>
          </div>
        );
      })}
    </div>,
    document.body,
  );
}
