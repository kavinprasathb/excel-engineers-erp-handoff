import { useCallback, useEffect, useState } from "react";

const KEY = "ee-sidebar-collapsed";

/** Persisted so the choice survives a reload; a failed read just means expanded. */
export function useSidebarCollapsed(): [boolean, () => void] {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(KEY) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(KEY, collapsed ? "1" : "0");
    } catch {
      // Private browsing: the choice just will not persist.
    }
  }, [collapsed]);

  const toggle = useCallback(() => setCollapsed((c) => !c), []);
  return [collapsed, toggle];
}
