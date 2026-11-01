import { useNotifications } from "./api";

/** The count beside "Notifications" in the nav: red when anything is urgent. */
export function NotificationBadge() {
  const n = useNotifications();
  const total = n.data?.total ?? 0;
  if (total === 0) return null;
  const urgent = (n.data?.counts.critical ?? 0) > 0;
  return (
    <span
      className={`min-w-6 shrink-0 rounded-md px-1.5 text-center text-[11px] font-medium leading-5 ${urgent ? "bg-red-bg text-red" : "bg-brand/10 text-brand"}`}
    >
      {total > 99 ? "99+" : total}
      <span className="sr-only"> notifications</span>
    </span>
  );
}
