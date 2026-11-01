import type { QuotationFormat } from "../../../api/types";
import { OFFER_LAYOUTS } from "../layouts";

/**
 * Three cards: how the offer letter is laid out. The items are the same in
 * every layout except that the technical sheet keeps its own grid editor, so
 * switching never loses data. Locked in a negotiation (prices only).
 */
export function OfferLayoutPicker({
  value,
  suggested,
  locked,
  onChange,
}: {
  value: QuotationFormat;
  suggested: QuotationFormat;
  locked: boolean;
  onChange: (value: QuotationFormat) => void;
}) {
  return (
    <div role="radiogroup" aria-label="Offer layout" className="grid gap-3 md:grid-cols-3">
      {OFFER_LAYOUTS.map((o) => {
        const on = value === o.value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={on}
            disabled={locked && !on}
            onClick={() => !locked && onChange(o.value)}
            className={`group relative flex gap-3 rounded-lg border p-3 text-left transition ${
              on
                ? "border-brand bg-brand/5 shadow-sm ring-1 ring-brand"
                : "border-line bg-card hover:border-brand/50 hover:bg-hoverfill"
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            <span
              className={`grid size-9 shrink-0 place-items-center rounded-md text-[15px] font-bold ${
                on ? "bg-brand text-white" : "bg-hoverfill text-ink-2"
              }`}
            >
              {o.letter}
            </span>
            <span className="min-w-0">
              <span className="flex items-center gap-2 text-[14px] font-semibold text-ink">
                {o.title}
                {suggested === o.value && !on ? (
                  <span className="rounded-full bg-amber-bg px-2 py-px text-[11px] font-medium text-amber">
                    Suggested
                  </span>
                ) : null}
              </span>
              <span className="mt-0.5 block text-[12.5px] leading-snug text-ink-2">{o.text}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
