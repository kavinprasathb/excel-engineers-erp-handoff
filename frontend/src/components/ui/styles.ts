/**
 * The design system, as class-name constants.
 *
 * Ported from MetricsGo v2's `components/shell/ui.tsx`. Deliberately strings
 * rather than wrapper components: composition is a template literal, so a page
 * can extend any of these without a `variant` prop existing for every case.
 *
 *   <div className={`${cardCls} p-5`}>
 *
 * Two radii only: rounded-xl (12px) for cards/panels/tables, rounded-lg (8px)
 * for buttons, inputs, dropdowns and nav items. Borders separate things, not
 * shadows. Focus turns the border brand-coloured; there are no focus rings.
 */

export const cardCls =
  "rounded-2xl border border-line bg-card shadow-[0_1px_2px_rgba(16,24,40,0.04),0_1px_3px_rgba(16,24,40,0.03)]";

export const inputCls =
  "w-full rounded-lg border border-line bg-card px-3 py-2 text-[13px] text-ink " +
  "placeholder-ink-2/60 outline-none transition-colors focus:border-brand " +
  "disabled:opacity-50";

export const labelCls = "mb-1.5 block text-xs font-medium text-ink-2";

/** Three-level button hierarchy: brand → inverting dark → bordered ghost. */
export const primaryBtnCls =
  "rounded-lg bg-darkbtn px-4 py-2 text-[13px] font-medium text-darkbtn-text " +
  "transition-colors hover:bg-darkbtn-hover disabled:opacity-50";

export const darkBtnCls =
  "rounded-lg bg-darkbtn px-4 py-2 text-[13px] font-semibold text-darkbtn-text " +
  "transition-colors hover:bg-darkbtn-hover disabled:opacity-50";

export const ghostBtnCls =
  "rounded-lg border border-line bg-card px-4 py-2 text-[13px] font-medium text-ink " +
  "transition-colors hover:bg-hoverfill disabled:opacity-50";

export const dangerBtnCls =
  "rounded-lg bg-red px-4 py-2 text-[13px] font-semibold text-white " +
  "transition-colors hover:opacity-90 disabled:opacity-50";

export const toastCls =
  "fixed bottom-6 right-6 z-50 rounded-full bg-darkbtn px-4 py-2 text-[13px] " +
  "font-medium text-darkbtn-text shadow-lg";

/** Segmented control: bordered container, pill options. */
export const segWrapCls =
  "inline-flex items-center gap-1 rounded-lg border border-line bg-app-bg p-1";
export const segItemActiveCls =
  "rounded-md border border-line bg-card px-3.5 py-1.5 text-[13px] font-medium text-ink";
export const segItemIdleCls =
  "rounded-md border border-transparent px-3.5 py-1.5 text-[13px] text-ink-2 " +
  "transition-colors hover:text-ink";

/** Table: the card is the scroll container; the table itself has no border. */
export const tableWrapCls =
  "overflow-x-auto rounded-2xl border border-line bg-card p-1.5 shadow-[0_1px_2px_rgba(16,24,40,0.04)]";
export const theadRowCls = "text-left text-[12px] text-ink-2";
export const tbodyRowCls =
  "border-b border-line/60 transition-colors last:border-0 hover:bg-hoverfill";
export const cellCls = "p-3";

/** Alert surface, e.g. a failed load. Error is never conflated with empty. */
export const errorCardCls = "rounded-xl border border-red/40 bg-red-bg/40 p-4";

export const eyebrowCls = "text-[13px] font-normal text-ink-2";

/* ------------------------------------------------------------------ *
 * Additions for the app shell. Same rules: borders not shadows, two
 * radii, transition-colors only.
 * ------------------------------------------------------------------ */

/**
 * Button sizes. The `min-h-11 md:min-h-*` pattern repeats across every
 * interactive primitive: 44px touch targets below `md`, the dense desktop
 * height above it. Density is a pointer affordance, not a phone one.
 */
export const btnSizeCls = {
  sm: "px-3 py-1.5 text-[13px] min-h-11 md:min-h-8",
  md: "px-4 py-2 text-[13px] min-h-11 md:min-h-9",
  lg: "px-5 py-2.5 text-[13px] min-h-11 md:min-h-10",
} as const;

export const btnBaseCls =
  "inline-flex items-center justify-center gap-2 rounded-lg font-medium " +
  "transition-colors outline-none focus-visible:border-brand " +
  "disabled:cursor-not-allowed disabled:opacity-50";

/** Variant colours only — size and base come from the constants above. */
export const btnVariantCls = {
  primary:
    "bg-darkbtn text-darkbtn-text font-medium border border-darkbtn hover:bg-darkbtn-hover",
  dark:
    "bg-darkbtn text-darkbtn-text font-semibold border border-darkbtn " +
    "hover:bg-darkbtn-hover",
  ghost: "border border-line bg-card text-ink hover:bg-hoverfill",
  danger: "bg-red text-white font-semibold border border-red hover:opacity-90",
} as const;

export const selectCls =
  "w-full appearance-none rounded-lg border border-line bg-card px-3 py-2 pr-9 " +
  "text-[13px] text-ink outline-none transition-colors focus:border-brand " +
  "disabled:opacity-50 min-h-11 md:min-h-9";

export const textareaCls =
  "w-full rounded-lg border border-line bg-card px-3 py-2 text-[13px] text-ink " +
  "placeholder-ink-2/60 outline-none transition-colors focus:border-brand " +
  "disabled:opacity-50 resize-y";

/** An input that must clear the same 44px bar as the buttons beside it. */
export const inputSizedCls = `${inputCls} min-h-11 md:min-h-9`;

/** Inline field error. Red text, never a red border alone — colour is not the
    only signal. */
export const fieldErrorCls = "mt-1.5 text-[12px] text-red";

export const modalBackdropCls =
  "fixed inset-0 z-40 bg-black/40 flex items-end sm:items-center sm:justify-center " +
  "sm:p-4 overflow-y-auto";

/** Full-width sheet on a phone, centred dialog from `sm` up. */
export const modalPanelCls =
  "relative z-50 w-full rounded-t-xl sm:rounded-xl border border-line bg-card " +
  "shadow-xl sm:max-w-lg";

/** Right rail on desktop, bottom sheet on a phone. */
export const drawerPanelCls =
  "fixed z-50 border-line bg-card shadow-xl " +
  "inset-x-0 bottom-0 max-h-[85vh] rounded-t-xl border-t " +
  "md:inset-y-0 md:left-auto md:right-0 md:max-h-none md:w-[26rem] md:rounded-none md:border-l md:border-t-0";

/** Nav item. Active is a soft grey fill; idle items stay dark enough to read. */
export const navItemBaseCls =
  "flex items-center gap-2.5 rounded-lg border px-2.5 text-[13.5px] font-medium " +
  "transition-colors min-h-11 md:min-h-8";
export const navItemActiveCls = "border-transparent bg-nav-active-bg font-medium text-nav-active-text";
export const navItemIdleCls =
  "border-transparent text-nav-idle hover:bg-hoverfill hover:text-ink";

/** The page gutter, stepped. Every page uses exactly this. */
export const gutterCls = "px-4 sm:px-6 lg:px-10";

export const pageHeadingCls = "font-display text-[24px] font-extrabold tracking-tight text-heading";

export const badgeToneCls = {
  green: "bg-green-bg text-green",
  red: "bg-red-bg text-red",
  amber: "bg-amber-bg text-amber",
  brand: "bg-brand/10 text-brand",
  gray: "bg-hoverfill text-ink-2",
} as const;

/** Full-width variant of segWrapCls. A separate constant rather than appending
    `flex w-full`, because two display utilities in one class list resolve by
    stylesheet order, not by the order they are written. */
export const segWrapFullCls =
  "flex w-full items-center gap-1 rounded-lg border border-line bg-app-bg p-1";
