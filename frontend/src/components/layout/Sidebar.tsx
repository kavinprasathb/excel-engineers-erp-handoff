import { NavLink, useLocation } from "react-router-dom";
import { itemForPath, sidebarGroups } from "./nav";
import type { NavItem } from "./nav";
import { useFoldedGroups } from "./useFoldedGroups";
import { NavCount } from "./NavCount";
import { useIsOwner, useLogout, useMe } from "../../features/auth/api";
import { ExcelLogo } from "../brand/ExcelLogo";
import { Icon } from "../ui/Icon";
import { navItemActiveCls, navItemBaseCls, navItemIdleCls } from "../ui/styles";

/**
 * Desktop only — below `md` the same nav is a drawer (see MobileNav).
 *
 * The daily work sits at the top in groups that fold; the group holding the
 * current page always stays open. Admin and the signed-in person are pinned
 * to the bottom, so the list fits one screen without scrolling.
 */
export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const owner = useIsOwner();
  const { pathname } = useLocation();
  const [folded, toggleGroup] = useFoldedGroups();
  const currentGroup = itemForPath(pathname)?.group;
  const groups = sidebarGroups(owner);
  // One scrolling list: Administration folds and scrolls like every other group.
  const main = groups;

  return (
    <aside
      // Pinned to the viewport so it never scrolls away under a long page.
      className={`sticky top-0 hidden h-dvh shrink-0 flex-col self-start border-r border-line bg-card transition-[width] md:flex ${
        collapsed ? "w-14" : "w-56"
      }`}
    >
      <div
        className={`flex shrink-0 items-center border-b border-line ${
          collapsed ? "flex-col justify-center gap-1 px-2 py-2" : "h-14 justify-between px-3"
        }`}
      >
        {collapsed ? <ExcelLogo variant="mark" size={26} /> : <ExcelLogo size={30} />}
        <button
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-pressed={collapsed}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-transparent text-ink-2 transition-colors hover:bg-hoverfill hover:text-ink"
        >
          <Icon name="panel" />
        </button>
      </div>

      <nav aria-label="Main" className="min-h-0 flex-1 overflow-y-auto px-2 pb-1">
        {main.map(([group, items]) => {
          const open = collapsed || group === currentGroup || !folded.has(group);
          return (
            <div key={group} className="pt-1 first:pt-0.5">
              {items.length === 1 && group === "Overview" ? null : collapsed ? (
                <div className="mx-2 mb-1 border-t border-line first:hidden" />
              ) : (
                <button
                  type="button"
                  onClick={() => toggleGroup(group)}
                  aria-expanded={open}
                  disabled={group === currentGroup}
                  className="flex w-full items-center gap-2 rounded-md px-2.5 py-0.5 font-display text-[11px] font-extrabold uppercase tracking-[0.1em] text-nav-section transition-colors hover:text-ink disabled:cursor-default"
                >
                  <span className="min-w-0 flex-1 truncate text-left">{group}</span>
                  {group === currentGroup ? null : (
                    <Icon name={open ? "chevronDown" : "chevronRight"} size={13} />
                  )}
                </button>
              )}
              {open ? (
                <div className="mt-0.5 space-y-0.5">
                  {items.map((item) => (
                    <Item key={item.to} item={item} collapsed={collapsed} />
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </nav>

      <div className="shrink-0 border-t border-line p-2">
        <Person collapsed={collapsed} />
      </div>
    </aside>
  );
}

function Item({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  return (
    <NavLink
      to={item.to}
      // Collapsed to icons: the tooltip names the page and its group.
      title={collapsed ? `${item.label} · ${item.group}` : undefined}
      className={({ isActive }) =>
        `${navItemBaseCls} ${isActive ? navItemActiveCls : navItemIdleCls} ${collapsed ? "justify-center" : ""}`
      }
    >
      <Icon name={item.icon} />
      {collapsed ? null : (
        <>
          <span className="min-w-0 flex-1 truncate">{item.label}</span>
          <NavCount to={item.to} />
        </>
      )}
    </NavLink>
  );
}

/** Who is signed in, and the way out, at the foot of the sidebar. */
function Person({ collapsed }: { collapsed: boolean }) {
  const { data: me } = useMe();
  const logout = useLogout();
  if (!me) return null;
  const name = me.full_name || me.email;
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <div className={`mt-1.5 flex items-center gap-2 rounded-lg bg-app-bg p-1 ${collapsed ? "flex-col" : ""}`}>
      <span
        className="grid size-8 shrink-0 place-items-center rounded-full bg-darkbtn text-[13px] font-semibold text-darkbtn-text"
        title={collapsed ? name : undefined}
      >
        {initial}
      </span>
      {collapsed ? null : (
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-medium text-ink">{name}</p>
          <p className="text-[11.5px] text-ink-2">{me.role === "admin" ? "Owner" : "Staff"}</p>
        </div>
      )}
      <button
        type="button"
        onClick={() => logout.mutate()}
        disabled={logout.isPending}
        aria-label="Sign out"
        title="Sign out"
        className="grid size-8 shrink-0 place-items-center rounded-lg text-ink-2 transition-colors hover:bg-card hover:text-ink disabled:opacity-50"
      >
        <Icon name="logout" size={16} />
      </button>
    </div>
  );
}
