import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { createPortal } from "react-dom";
import { sidebarGroups } from "./nav";
import { NavCount } from "./NavCount";
import { useIsOwner } from "../../features/auth/api";
import { ExcelLogo } from "../brand/ExcelLogo";
import { Icon } from "../ui/Icon";
import { navItemActiveCls, navItemBaseCls, navItemIdleCls } from "../ui/styles";
import { useBodyScrollLock, useEscapeKey, useFocusTrap } from "../../lib/overlay";

/**
 * The sub-`md` nav: a sticky bar with a hamburger opening a full-height
 * slide-over. Deliberately not the shared `Drawer` — that one is a bottom
 * sheet on a phone, and a nine-item nav wants the vertical run.
 */
export function MobileNav({ actions }: { actions?: React.ReactNode }) {
  const groups = sidebarGroups(useIsOwner());
  const location = useLocation();
  // The panel remembers which route it was opened on, so navigating away
  // closes it as a matter of derivation rather than an effect chasing the
  // location. Tapping a link does not unmount this component, so something has
  // to notice.
  const [openedAt, setOpenedAt] = useState<string | null>(null);
  const open = openedAt === location.pathname;

  const setOpen = (next: boolean) => setOpenedAt(next ? location.pathname : null);

  const panelRef = useFocusTrap(open);
  useBodyScrollLock(open);
  useEscapeKey(open, () => setOpen(false));

  return (
    <>
      <div className="sticky top-0 z-30 flex h-14 items-center justify-between gap-2 border-b border-line bg-card px-4 md:hidden">
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open navigation"
          aria-expanded={open}
          className="-ml-2 flex h-11 w-11 items-center justify-center rounded-lg border border-transparent text-ink transition-colors hover:bg-hoverfill"
        >
          <Icon name="menu" size={19} />
        </button>
        <span className="flex min-w-0 flex-1 items-center">
          <ExcelLogo size={26} />
        </span>
        {actions}
      </div>

      {open
        ? createPortal(
            <div className="md:hidden">
              <div
                className="fixed inset-0 z-40 bg-black/40"
                onMouseDown={() => setOpen(false)}
                aria-hidden="true"
              />
              <div
                ref={panelRef}
                role="dialog"
                aria-modal="true"
                aria-label="Navigation"
                tabIndex={-1}
                className="fixed inset-y-0 left-0 z-50 flex w-64 max-w-[85vw] flex-col border-r border-line bg-card shadow-xl"
              >
                <div className="flex h-14 items-center justify-between border-b border-line px-3">
                  <ExcelLogo size={28} />
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    aria-label="Close navigation"
                    className="-mr-1 flex h-11 w-11 items-center justify-center rounded-lg border border-transparent text-ink-2 transition-colors hover:bg-hoverfill hover:text-ink"
                  >
                    <Icon name="close" />
                  </button>
                </div>

                <nav aria-label="Main" className="flex-1 overflow-y-auto px-2 pb-2">
                  {groups.map(([group, list]) => (
                    <div key={group} className="pt-3">
                      <p className="px-2.5 pb-1 font-display text-[11px] font-extrabold uppercase tracking-[0.1em] text-nav-section">{group}</p>
                      <div className="space-y-0.5">
                        {list.map((item) => (
                          <NavLink
                            key={item.to}
                            to={item.to}
                            className={({ isActive }) =>
                              `${navItemBaseCls} ${isActive ? navItemActiveCls : navItemIdleCls}`
                            }
                          >
                            <Icon name={item.icon} />
                            <span className="min-w-0 flex-1 truncate">{item.label}</span>
                            <NavCount to={item.to} />
                          </NavLink>
                        ))}
                      </div>
                    </div>
                  ))}
                </nav>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
