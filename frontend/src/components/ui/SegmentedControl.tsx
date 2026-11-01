import { segItemActiveCls, segItemIdleCls, segWrapCls, segWrapFullCls } from "./styles";

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

export interface SegmentedControlProps<T extends string> {
  value: T;
  options: readonly SegmentedOption<T>[];
  onChange: (value: T) => void;
  /** Accessible name for the group; there is no visible legend. */
  label: string;
  /** Below `md` a three-option control at 360px needs the full width. */
  fullWidth?: boolean;
}

export function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
  label,
  fullWidth = false,
}: SegmentedControlProps<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={fullWidth ? segWrapFullCls : segWrapCls}
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            className={`${active ? segItemActiveCls : segItemIdleCls} min-h-9 ${
              fullWidth ? "flex-1" : ""
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
