import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { Page, QuotationSummary } from "../../api/types";
import { useIsOwner } from "../../features/auth/api";
import { useBodyScrollLock, useEscapeKey, useFocusTrap } from "../../lib/overlay";
import { Icon } from "../ui/Icon";
import type { IconName } from "../ui/Icon";
import { visibleItems } from "./nav";

interface Hit {
  key: string;
  label: string;
  hint: string;
  icon: IconName;
  to: string;
}

/**
 * Ctrl+K (or the search box in the top bar): type a page name or a quote
 * number, press Enter, you are there.
 */
export function QuickJump() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-9 w-64 items-center gap-2 rounded-lg border border-line bg-app-bg px-3 text-[13px] text-ink-2 transition-colors hover:bg-hoverfill"
      >
        <Icon name="search" size={15} />
        <span className="flex-1 text-left">Search or jump to…</span>
        <kbd className="rounded border border-line bg-card px-1.5 text-[11px] text-ink-2">Ctrl K</kbd>
      </button>
      {open ? <Palette onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function Palette({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const owner = useIsOwner();
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const panelRef = useFocusTrap(true);
  useBodyScrollLock(true);
  useEscapeKey(true, onClose);

  const needle = q.trim().toLowerCase();
  const quotes = useQuery({
    meta: { silent: true },
    queryKey: ["quick-jump", needle],
    enabled: needle.length >= 2,
    queryFn: ({ signal }) =>
      api.get<Page<QuotationSummary>>("/quotations", { q: needle, page_size: 6 }, signal),
  });

  const hits = useMemo<Hit[]>(() => {
    const pages = visibleItems(owner)
      .filter((i) => !needle || i.label.toLowerCase().includes(needle) || i.group.toLowerCase().includes(needle))
      .map((i) => ({ key: i.to, label: i.label, hint: i.group, icon: i.icon, to: i.to }));
    const qs = (needle.length >= 2 ? (quotes.data?.items ?? []) : []).map((x) => ({
      key: `q-${x.id}`,
      label: x.number,
      hint: `Quotation · ${x.customer.name}`,
      icon: "quotations" as IconName,
      to: `/quotations/${x.id}`,
    }));
    return [...pages, ...qs];
  }, [needle, owner, quotes.data]);

  const pick = Math.min(active, Math.max(hits.length - 1, 0));

  function go(hit: Hit | undefined) {
    if (!hit) return;
    onClose();
    navigate(hit.to);
  }

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 p-4 pt-[12vh]" onMouseDown={onClose}>
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Search or jump to"
        tabIndex={-1}
        onMouseDown={(e) => e.stopPropagation()}
        className="w-full max-w-lg overflow-hidden rounded-2xl border border-line bg-card shadow-2xl"
      >
        <div className="flex items-center gap-2 border-b border-line px-4">
          <Icon name="search" size={16} className="text-ink-2" />
          <input
            autoFocus
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setActive(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((a) => Math.min(a + 1, hits.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((a) => Math.max(a - 1, 0));
              } else if (e.key === "Enter") {
                e.preventDefault();
                go(hits[pick]);
              }
            }}
            placeholder="Page name or quote number…"
            aria-label="Search pages and quotations"
            className="h-12 w-full bg-transparent text-[14px] text-ink outline-none placeholder:text-ink-2/70"
          />
        </div>
        <ul className="max-h-80 overflow-y-auto p-1.5">
          {hits.length === 0 ? (
            <li className="px-3 py-6 text-center text-[13px] text-ink-2">
              {quotes.isFetching ? "Searching…" : "Nothing found."}
            </li>
          ) : (
            hits.map((h, i) => (
              <li key={h.key}>
                <button
                  type="button"
                  onMouseEnter={() => setActive(i)}
                  onClick={() => go(h)}
                  className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-[13px] ${
                    i === pick ? "bg-hoverfill" : ""
                  }`}
                >
                  <Icon name={h.icon} size={16} className="text-ink-2" />
                  <span className="min-w-0 flex-1 truncate text-ink">{h.label}</span>
                  <span className="shrink-0 text-[12px] text-ink-2">{h.hint}</span>
                </button>
              </li>
            ))
          )}
        </ul>
        <p className="border-t border-line px-4 py-2 text-[11.5px] text-ink-2">↑ ↓ to move · Enter to open · Esc to close</p>
      </div>
    </div>,
    document.body,
  );
}
