import { useDebouncedValue } from "../../../lib/useDebouncedValue";
import { useItemSuggestions } from "../api";
import { formatRupees } from "../format";
import type { ItemSuggestion } from "../../../api/types";

function shortDate(iso: string | null): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

/**
 * Under a line's description while it is being typed: what was quoted before
 * with the same words, from the client's past offer letters and from
 * quotations made in the app. Each shows the rate, MOC, HSN, the customer it
 * went to and when; the customer being quoted comes first. Picking one fills
 * the line; everything stays editable. Reading only: nothing is saved here.
 */
export function DescriptionSuggestions({
  label,
  text,
  customerId,
  onPick,
  onClose,
}: {
  /** "Item 2": prefixes the accessible name. */
  label: string;
  text: string;
  customerId: number | null;
  onPick: (s: ItemSuggestion) => void;
  onClose: () => void;
}) {
  const q = useDebouncedValue(text, 250);
  const res = useItemSuggestions(q, customerId);
  // Anything but a list (an error page, an old server) shows nothing rather than failing.
  const items = Array.isArray(res.data) ? res.data : [];
  if (q.trim().length < 3 || items.length === 0) return null;

  return (
    <div className="relative">
      <ul
        role="listbox"
        aria-label={`${label} earlier quotes`}
        className="absolute z-30 mt-1 max-h-80 w-full min-w-[22rem] overflow-auto rounded-lg border border-line bg-card shadow-xl"
      >
        <li className="flex items-center justify-between border-b border-line bg-hoverfill px-3 py-1.5 text-[11.5px] font-medium uppercase tracking-wide text-ink-2">
          Quoted before
          <button type="button" className="normal-case text-brand hover:underline" onMouseDown={(e) => e.preventDefault()} onClick={onClose}>
            Close
          </button>
        </li>
        {items.map((s, i) => (
          <li key={`${s.offer_no}-${i}`}>
            <button
              type="button"
              role="option"
              aria-selected={false}
              // Keep the description box focused, so the click lands.
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => onPick(s)}
              className="block w-full border-b border-line/60 px-3 py-2 text-left last:border-0 hover:bg-hoverfill"
            >
              <span className="flex items-start justify-between gap-3">
                <span className="min-w-0">
                  <span className="block truncate text-[13px] font-medium text-ink">{s.description}</span>
                  {s.details ? <span className="block truncate text-[11.5px] text-ink-2">{s.details}</span> : null}
                </span>
                <span className="shrink-0 text-right text-[13px] font-semibold tabular-nums text-ink">
                  {formatRupees(s.rate_paise)}
                  {s.unit ? <span className="block text-[11px] font-normal text-ink-2">per {s.unit}</span> : null}
                </span>
              </span>
              <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11.5px] text-ink-2">
                {s.same_customer ? (
                  <span className="rounded-full bg-green-bg px-1.5 py-px font-medium text-green">This customer</span>
                ) : null}
                <span className="font-medium text-ink">{s.customer_name || "—"}</span>
                {s.offer_date ? <span>· {shortDate(s.offer_date)}</span> : null}
                {s.offer_no ? <span>· {s.offer_no}</span> : null}
                {s.moc ? <span>· MOC {s.moc}</span> : null}
                {s.part_no ? <span>· Part {s.part_no}</span> : null}
                {s.hsn_code ? <span>· HSN {s.hsn_code}</span> : null}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
