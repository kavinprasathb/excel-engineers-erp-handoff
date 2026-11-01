/**
 * DELIBERATE NARROW EXCEPTION to "loading is the word Loading…".
 *
 * Page and table loading states still render the plain word — see `Loading`
 * below, which is what almost every screen should use. This spinner exists
 * only for the inside of a button that has already been pressed, where the
 * word would resize the button and the user needs feedback tied to the control
 * they just touched. Do not reach for it anywhere else.
 */

export function Spinner({ size = 14, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      className={`animate-spin ${className}`}
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="12" cy="12" r="9" className="opacity-25" />
      <path d="M21 12a9 9 0 0 0-9-9" />
    </svg>
  );
}

/** The house loading state: a word, in secondary ink. */
export function Loading({ className = "" }: { className?: string }) {
  return (
    <p role="status" className={`text-[13px] text-ink-2 ${className}`}>
      Loading…
    </p>
  );
}
