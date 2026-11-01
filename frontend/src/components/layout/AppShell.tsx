import { useEffect } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { itemForPath } from "./nav";
import { QuickJump } from "./QuickJump";
import { NotificationBadge } from "../../features/notifications/NotificationBadge";
import { useSidebarCollapsed } from "./useSidebarCollapsed";
import { MobileNav } from "./MobileNav";
import { DailyNotice } from "../../features/notifications/DailyNotice";
import { Icon } from "../ui/Icon";
import { gutterCls } from "../ui/styles";
import { useLogout } from "../../features/auth/api";
import { ThemeToggle } from "./ThemeToggle";
import { registerNavigate } from "../../lib/navigation";

/**
 * Sidebar + top bar + content. The page header is rendered by each page rather
 * than here, because the title and its actions belong to the page's own data.
 */
export function AppShell() {
  const [collapsed, toggle] = useSidebarCollapsed();
  const navigate = useNavigate();

  // Lets the QueryClient's 401 handler redirect through the router instead of
  // a full page load.
  useEffect(() => {
    registerNavigate(navigate);
    return () => registerNavigate(null);
  }, [navigate]);

  return (
    <div className="flex min-h-dvh bg-app-bg">
      <Sidebar collapsed={collapsed} onToggle={toggle} />

      {/* min-w-0 or a wide table inside would stretch this column past the
          viewport and reintroduce the page-level horizontal scroll. */}
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileNav
          actions={
            <div className="flex items-center gap-2">
              <ThemeToggle compact />
              <BellLink compact />
              <LogoutButton compact />
            </div>
          }
        />
        <TopBar />
        <main className="flex-1">
          <Outlet />
        </main>
        <DailyNotice />
      </div>
    </div>
  );
}

function TopBar() {
  const { pathname } = useLocation();
  // The page you are on, named the way the sidebar names it.
  const page = itemForPath(pathname);

  return (
    <div
      className={`sticky top-0 z-30 hidden h-14 shrink-0 items-center gap-3 border-b border-line bg-card/90 backdrop-blur md:flex ${gutterCls}`}
    >
      {page ? (
        <div className="mr-auto flex min-w-0 items-center gap-2 text-[13.5px] text-ink">
          <Icon name={page.icon} className="text-ink-2" />
          <span className="truncate">{page.label}</span>
        </div>
      ) : (
        <div className="mr-auto" />
      )}
      <QuickJump />
      <ThemeToggle />
      <BellLink />
      <LogoutButton />
    </div>
  );
}

/** Notifications live on the bell: the count shows what is waiting. */
function BellLink({ compact = false }: { compact?: boolean }) {
  return (
    <Link
      to="/notifications"
      aria-label="Notifications"
      title="Notifications"
      className={`relative flex items-center justify-center rounded-lg border border-line bg-card text-ink transition-colors hover:bg-hoverfill ${
        compact ? "size-11" : "size-9"
      }`}
    >
      <Icon name="bell" size={17} />
      <span className="absolute -right-1.5 -top-1.5">
        <NotificationBadge />
      </span>
    </Link>
  );
}

function LogoutButton({ compact = false }: { compact?: boolean }) {
  const logout = useLogout();

  return (
    <button
      type="button"
      onClick={() => logout.mutate()}
      disabled={logout.isPending}
      aria-label="Log out"
      title="Log out"
      className={`flex items-center gap-2 rounded-lg border border-line bg-card px-3 text-[13px] font-medium text-ink transition-colors hover:bg-hoverfill disabled:opacity-50 ${
        compact ? "min-h-11" : "min-h-9"
      }`}
    >
      <Icon name="logout" />
      {compact ? null : "Log out"}
    </button>
  );
}
