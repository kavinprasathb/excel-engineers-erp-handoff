import { Icon } from "../ui/Icon";
import { useTheme } from "../../lib/theme";

/** Flips between explicit light and dark; Settings keeps the "System" option. */
export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { resolved, setPref } = useTheme();
  const dark = resolved === "dark";
  const label = dark ? "Switch to light mode" : "Switch to dark mode";

  return (
    <button
      type="button"
      onClick={() => setPref(dark ? "light" : "dark")}
      aria-label={label}
      title={label}
      className={`flex items-center justify-center rounded-lg border border-line bg-card text-ink transition-colors hover:bg-hoverfill ${
        compact ? "size-11" : "size-9"
      }`}
    >
      <Icon name={dark ? "sun" : "moon"} size={17} />
    </button>
  );
}
