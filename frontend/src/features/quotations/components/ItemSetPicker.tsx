import { useEffect, useRef, useState } from "react";
import { Button } from "../../../components/ui/Button";
import { Input } from "../../../components/ui/Input";
import { Icon } from "../../../components/ui/Icon";
import { useDebouncedCallback } from "../../../lib/useDebouncedCallback";
import { useProductLookup } from "../api";
import { joinedNames } from "../draft";
import type { DraftComponent } from "../draft";
import type { ProductLookup } from "../../../api/types";

/**
 * The items of one quotation line, picked from Inventory: a search box, an
 * Add button, the picked items as chips (each with its quantity per unit of
 * the line and a remove ×), and Finalise Description, which writes the
 * names, comma-separated, into the line's description.
 *
 * Picking, adding, removing and finalising never touch stock: the items are
 * kept by their inventory id, and stock moves only when the accepted
 * quotation's order is delivered. The description is for the letter only.
 */
export function ItemSetPicker({
  label,
  components,
  description,
  finalisedText,
  locked,
  onChange,
  onFinalise,
  onCustomize,
}: {
  /** "Item 2": prefixes every accessible name. */
  label: string;
  components: DraftComponent[];
  description: string;
  /** The text the last Finalise wrote; "" if none. Anything else in the box is the user's own. */
  finalisedText: string;
  /** Read-only, or a negotiation (prices only): the items cannot change. */
  locked: boolean;
  onChange: (components: DraftComponent[]) => void;
  onFinalise: (text: string) => void;
  onCustomize: () => void;
}) {
  const [text, setText] = useState("");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<ProductLookup | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmReplace, setConfirmReplace] = useState(false);
  const commit = useDebouncedCallback(setQuery, 250);
  const wrap = useRef<HTMLDivElement>(null);
  const results = useProductLookup(query);
  const items = results.data ?? [];

  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  const combined = joinedNames(components);
  // Finalised: the description is what the last Finalise wrote for these items.
  const finalised = components.length > 0 && finalisedText !== "" && finalisedText === combined;
  // The box holds the user's own words (typed, or edited after finalising).
  const ownWords = description.trim() !== "" && description !== finalisedText && description !== combined;

  function add(p: ProductLookup | null) {
    if (!p) return;
    if (components.some((c) => c.product_id === p.id)) {
      setNotice(`${p.name} is already in this line.`);
    } else {
      setNotice(null);
      onChange([
        ...components,
        {
          product_id: p.id,
          name: p.name,
          quantity: "1",
          // Only shelf items can be "out of stock"; a to-order item at 0 is normal.
          available: p.stock_type && p.stock_type !== "stocked" ? undefined : p.quantity_available,
          price: p.sell_price,
        },
      ]);
    }
    setPicked(null);
    setText("");
    setQuery("");
    setOpen(false);
  }

  function finalise() {
    if (components.length === 0) return;
    // Never overwrite the user's own text without asking.
    if (ownWords && !confirmReplace) {
      setConfirmReplace(true);
      return;
    }
    setConfirmReplace(false);
    onFinalise(combined);
  }

  if (locked && components.length === 0) return null;

  return (
    <div className="mt-2 space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        {locked ? null : (
          <div ref={wrap} className="relative w-full sm:w-64">
            <Input
              aria-label={`${label} search inventory`}
              placeholder="Search inventory…"
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                setPicked(null);
                commit(e.target.value);
                setOpen(true);
              }}
              onFocus={() => setOpen(true)}
              onKeyDown={(e) => {
                if (e.key === "Escape") setOpen(false);
                if (e.key === "Enter") {
                  e.preventDefault();
                  add(picked ?? items[0] ?? null);
                }
              }}
            />
            {open && query.trim() ? (
              <ul
                role="listbox"
                aria-label={`${label} inventory matches`}
                className="absolute z-20 mt-1 max-h-64 w-full min-w-[16rem] overflow-auto rounded-md border border-line bg-card shadow-lg"
              >
                {results.isPending ? (
                  <li className="px-3 py-2 text-[13px] text-ink-2">Searching…</li>
                ) : items.length === 0 ? (
                  <li className="px-3 py-2 text-[13px] text-ink-2">Nothing in inventory matches.</li>
                ) : (
                  items.map((p) => (
                    <li key={p.id}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={picked?.id === p.id}
                        className="block w-full px-3 py-2 text-left hover:bg-hoverfill"
                        onClick={() => {
                          setPicked(p);
                          setText(p.name);
                          setOpen(false);
                        }}
                      >
                        <span className="block truncate text-[13px] font-medium text-ink">{p.name}</span>
                        <span className={`block truncate text-[12px] ${p.quantity_available > 0 ? "text-ink-2" : "text-amber"}`}>
                          {p.sku} · {p.quantity_available > 0 ? `${p.quantity_available} in stock` : "Out of stock"}
                        </span>
                      </button>
                    </li>
                  ))
                )}
              </ul>
            ) : null}
          </div>
        )}
        {locked ? null : (
          <Button size="sm" onClick={() => add(picked ?? items[0] ?? null)} disabled={!text.trim()}>
            <Icon name="plus" size={14} />
            Add
          </Button>
        )}

        {/* The picked items, one line; wraps on a narrow screen. */}
        <ul className="flex flex-wrap items-center gap-1.5" aria-label={`${label} items`}>
          {components.map((c) => {
            const out = c.available !== undefined && c.available <= 0;
            return (
              <li
                key={c.product_id}
                className={`inline-flex items-center gap-1 rounded-full border py-0.5 pl-2.5 pr-1 text-[12.5px] ${out ? "border-amber/40 bg-amber-bg" : "border-line bg-hoverfill"}`}
                title={out ? `${c.name} is out of stock; the order will wait for it.` : undefined}
              >
                <span className="text-ink">{c.name}</span>
                {/* Not a quantity of the quote: how many of this go into one unit of the line. */}
                <span className="text-ink-2" aria-hidden>
                  ×
                </span>
                <input
                  aria-label={`${c.name} quantity per unit`}
                  inputMode="numeric"
                  className="w-9 rounded border border-line bg-card px-1 text-center text-[12.5px] tabular-nums text-ink read-only:border-transparent read-only:bg-transparent"
                  value={c.quantity}
                  readOnly={locked || finalised}
                  onChange={(e) =>
                    onChange(components.map((x) => (x.product_id === c.product_id ? { ...x, quantity: e.target.value } : x)))
                  }
                />
                {out ? <span className="text-[11px] font-medium text-amber">Out of stock</span> : null}
                {locked || finalised ? null : (
                  <button
                    type="button"
                    aria-label={`Remove ${c.name}`}
                    className="grid size-5 place-items-center rounded-full text-ink-2 hover:bg-card hover:text-ink"
                    onClick={() => {
                      setNotice(null);
                      onChange(components.filter((x) => x.product_id !== c.product_id));
                    }}
                  >
                    <Icon name="close" size={12} />
                  </button>
                )}
              </li>
            );
          })}
        </ul>

        {locked ? null : finalised ? (
          <span className="inline-flex gap-1.5">
            <Button size="sm" onClick={onCustomize} title="Add words, reword or edit the description">
              Customize
            </Button>
            <Button size="sm" onClick={() => onFinalise("")} title="Add, remove or change the items again">
              Change items
            </Button>
          </span>
        ) : (
          <Button
            size="sm"
            variant="primary"
            onClick={finalise}
            disabled={components.length === 0}
            title={components.length === 0 ? "Add at least one item first" : "Put the item names in the description"}
          >
            Finalise Description
          </Button>
        )}
      </div>

      {confirmReplace ? (
        <div role="alert" className="flex flex-wrap items-center gap-2 rounded-md border border-amber/30 bg-amber-bg px-2.5 py-1.5 text-[12.5px] text-ink">
          <span>The description has your own edits. Replace it with “{combined}”?</span>
          <Button size="sm" variant="primary" onClick={() => { setConfirmReplace(false); onFinalise(combined); }}>
            Replace
          </Button>
          <Button size="sm" onClick={() => setConfirmReplace(false)}>
            Keep my text
          </Button>
        </div>
      ) : null}
      {notice ? <p className="text-[12px] text-amber">{notice}</p> : null}
      {!locked && components.length > 0 && !finalised && finalisedText !== "" ? (
        <p className="text-[12px] text-ink-2">The items changed since the description was finalised. Finalise again to update it.</p>
      ) : null}
    </div>
  );
}
