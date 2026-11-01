export interface ExcelLogoProps {
  /** "full" shows the wordmark beside the mark; "mark" is the X alone. */
  variant?: "full" | "mark";
  /** Height of the mark in pixels; the wordmark scales with it. */
  size?: number;
  /** White wordmark and a lighter mark, for dark or blue backgrounds. */
  light?: boolean;
  className?: string;
}

/**
 * The Excel Engineers logo: the navy italic E with its grey speed lines,
 * "Excel Engineers" and "Total solutions in fluid mechanics" (vector files in
 * public/brand, rebuilt from the company's artwork so they stay sharp).
 * "full" is the whole logo; "mark" is the E alone, as in the browser icon.
 * In the dark theme, or with `light` on a dark background, the white version
 * is shown so the navy never disappears.
 */
export function ExcelLogo({ variant = "full", size = 36, light = false, className = "" }: ExcelLogoProps) {
  if (variant === "mark") {
    return (
      <img
        src="/brand/excel-mark.svg"
        alt="Excel Engineers"
        width={size}
        height={size}
        className={`shrink-0 ${className}`}
      />
    );
  }
  // The logo is 611 x 128; `size` is the height of its E, about 70% of it.
  const height = Math.round(size * 1.35);
  const width = Math.round((height * 611) / 128);
  const common = { alt: "Excel Engineers", width, height } as const;
  return (
    <span className={`inline-flex shrink-0 ${className}`}>
      {light ? (
        <img src="/brand/excel-logo-light.svg" {...common} />
      ) : (
        <>
          <img src="/brand/excel-logo.svg" className="logo-on-light" {...common} />
          <img src="/brand/excel-logo-light.svg" className="logo-on-dark" {...common} />
        </>
      )}
    </span>
  );
}

/** A simple "KSB Authorized Dealer" badge. Not KSB's own artwork. */
export function KsbDealer({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`} role="img" aria-label="KSB Authorized Dealer">
      <svg viewBox="0 0 24 24" width={26} height={26} aria-hidden="true" className="shrink-0">
        <rect x="2" y="2" width="20" height="20" rx="2" fill="none" stroke="#1d5fc4" strokeWidth="2.4" />
        <rect x="8" y="8" width="8" height="8" fill="#1d5fc4" />
      </svg>
      <span className="flex flex-col leading-none" aria-hidden="true">
        <span className="font-display text-[20px] font-extrabold tracking-[0.06em] text-[#1d5fc4]">KSB</span>
        <span className="mt-1 text-[10.5px] font-medium tracking-wide text-logo-2/80">Authorized Dealer</span>
      </span>
    </span>
  );
}
