import { useEffect, useRef } from "react";

/**
 * Overlay plumbing shared by Modal, Drawer and the mobile nav. All three need
 * the same four behaviours, and having them diverge is how one of them ends up
 * leaving the body permanently unscrollable.
 */

let lockCount = 0;
let previousOverflow = "";

/** Reference-counted so a drawer opened over a modal does not unlock early. */
export function useBodyScrollLock(active: boolean): void {
  useEffect(() => {
    if (!active) return;
    if (lockCount === 0) {
      previousOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
    }
    lockCount += 1;
    return () => {
      lockCount -= 1;
      if (lockCount === 0) document.body.style.overflow = previousOverflow;
    };
  }, [active]);
}

export function useEscapeKey(active: boolean, onEscape: () => void): void {
  // Kept in a ref so a fresh inline callback does not re-bind the listener on
  // every render. Assigned in an effect, never during render.
  const handler = useRef(onEscape);
  useEffect(() => {
    handler.current = onEscape;
  }, [onEscape]);

  useEffect(() => {
    if (!active) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        handler.current();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [active]);
}

const FOCUSABLE =
  'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),' +
  'textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

/**
 * Moves focus into the panel on open, cycles Tab inside it, and restores focus
 * to whatever was focused before — otherwise closing a dialog dumps the user
 * at the top of the document.
 */
export function useFocusTrap(active: boolean) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!active) return;
    const panel = ref.current;
    if (!panel) return;

    const restoreTo = document.activeElement;
    const first = panel.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? panel).focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const items = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (el) => el.offsetParent !== null || el === document.activeElement,
      );
      if (items.length === 0) {
        e.preventDefault();
        return;
      }
      const head = items[0];
      const tail = items[items.length - 1];
      if (e.shiftKey && document.activeElement === head) {
        e.preventDefault();
        tail.focus();
      } else if (!e.shiftKey && document.activeElement === tail) {
        e.preventDefault();
        head.focus();
      }
    };

    panel.addEventListener("keydown", onKeyDown);
    return () => {
      panel.removeEventListener("keydown", onKeyDown);
      if (restoreTo instanceof HTMLElement) restoreTo.focus();
    };
  }, [active]);

  return ref;
}
