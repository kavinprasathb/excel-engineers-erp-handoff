import { useEffect, useRef, useState } from "react";
import { Input } from "../../../components/ui/Input";
import { useDebouncedCallback } from "../../../lib/useDebouncedCallback";
import { formatMoney } from "../../../lib/format";
import { useProductLookup } from "../api";
import { stockTypeLabel } from "../../../api/types";
import type { ProductLookup } from "../../../api/types";
import { QuickAddItem } from "../../products/components/QuickAddItem";

/**
 * Type-ahead over the catalogue. Picking a product adds a line with its name
 * and list price filled in; both stay editable afterwards, so this is a
 * shortcut, not a lock.
 */
export function ProductPicker({
  onPick,
  disabled,
}: {
  onPick: (product: ProductLookup) => void;
  disabled?: boolean;
}) {
  const [text, setText] = useState("");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);
  const commit = useDebouncedCallback(setQuery, 250);
  const wrap = useRef<HTMLDivElement>(null);
  const results = useProductLookup(query);

  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  function pick(p: ProductLookup) {
    onPick(p);
    setText("");
    setQuery("");
    setOpen(false);
  }

  const items = results.data ?? [];

  return (
    <div ref={wrap} className="relative">
      <Input
        aria-label="Add from catalogue"
        placeholder="Add from catalogue — type a name, SKU or model"
        value={text}
        disabled={disabled}
        onChange={(e) => {
          setText(e.target.value);
          commit(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false);
          if (e.key === "Enter" && items.length > 0) {
            e.preventDefault();
            pick(items[0]);
          }
        }}
      />
      {open && query.trim() ? (
        <ul
          role="listbox"
          aria-label="Catalogue matches"
          className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-md border border-line bg-card shadow-lg"
        >
          {results.isPending ? (
            <li className="px-3 py-2 text-[13px] text-ink-2">Searching…</li>
          ) : items.length === 0 ? (
            <>
              <li className="px-3 py-2 text-[13px] text-ink-2">Nothing in inventory matches.</li>
              <li>
                <button
                  type="button"
                  className="block w-full border-t border-line bg-hoverfill px-3 py-2 text-left text-[13px] font-medium text-brand"
                  onClick={() => {
                    setAdding(text.trim());
                    setOpen(false);
                  }}
                >
                  + Add “{text.trim()}” as a new item
                </button>
              </li>
            </>
          ) : (
            items.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={false}
                  className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-hoverfill"
                  onClick={() => pick(p)}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-[13px] font-medium text-ink">{p.name}</span>
                    <span className="block truncate text-[12px] text-ink-2">
                      {p.sku}
                      {p.model_number ? ` · ${p.model_number}` : ""} ·{" "}
                      {p.stock_type && p.stock_type !== "stocked"
                        ? stockTypeLabel(p.stock_type)
                        : `${p.quantity_available} in stock`}
                    </span>
                  </span>
                  <span className="shrink-0 text-[13px] tabular-nums text-ink">
                    {formatMoney(p.sell_price)}
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}
      {adding !== null ? (
        <QuickAddItem
          initialName={adding}
          onCancel={() => setAdding(null)}
          onAdded={(item) => {
            setAdding(null);
            pick(item);
          }}
        />
      ) : null}
    </div>
  );
}
