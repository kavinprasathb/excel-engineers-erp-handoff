import { ICON_PATHS } from "./icon-paths";
import type { IconName } from "./icon-paths";

// Re-exported so consumers need only know about <Icon>.
export type { IconName };

export interface IconProps {
  name: IconName;
  /** Pixels. 17 is the app-wide default and rarely wants overriding. */
  size?: number;
  className?: string;
  /** Icons are decorative unless given a label. */
  title?: string;
}

export function Icon({ name, size = 17, className = "", title }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`shrink-0 ${className}`}
      aria-hidden={title ? undefined : true}
      role={title ? "img" : undefined}
      focusable="false"
    >
      {title ? <title>{title}</title> : null}
      {ICON_PATHS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
