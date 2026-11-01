import { createContext, useContext } from "react";

export type ToastTone = "default" | "success" | "error";

export interface ToastItem {
  id: number;
  message: string;
  tone: ToastTone;
}

export interface ToastApi {
  show: (message: string, tone?: ToastTone) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  dismiss: (id: number) => void;
}

export const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>.");
  return ctx;
}

/**
 * The QueryClient's global error handler lives outside React, so it cannot
 * call the hook. The provider parks its `show` here on mount and the handler
 * reaches it through this slot. Deliberately one slot, not a list: there is
 * exactly one provider, at the root.
 */
let externalShow: ToastApi["show"] | null = null;

export function registerToastSink(show: ToastApi["show"] | null): void {
  externalShow = show;
}

export function toastFromOutsideReact(message: string, tone: ToastTone = "default"): void {
  externalShow?.(message, tone);
}
