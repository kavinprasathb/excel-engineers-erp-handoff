import { useNotifications } from "../../features/notifications/api";

// Work waiting behind a nav item, read from the notifications already loaded.
const WAITING: Record<string, (key: string) => boolean> = {
  "/orders": (k) => k.startsWith("order-ready-"),
  "/purchase-orders": (k) => k.startsWith("po-unsent-") || k.startsWith("po-nosupplier-"),
  "/quotations": (k) => k.startsWith("quote-noreply-"),
  "/negotiations": (k) => k.startsWith("quote-stuck-"),
};

/** A small count beside a sidebar item when something there needs doing. */
export function NavCount({ to }: { to: string }) {
  const n = useNotifications();
  const match = WAITING[to];
  if (!match || !n.data) return null;
  const count = n.data.items.filter((i) => match(i.key)).length;
  if (count === 0) return null;
  return (
    <span className="min-w-5 shrink-0 rounded-md bg-brand/10 px-1.5 text-center text-[11px] font-medium leading-5 text-brand">
      {count}
      <span className="sr-only"> waiting</span>
    </span>
  );
}
