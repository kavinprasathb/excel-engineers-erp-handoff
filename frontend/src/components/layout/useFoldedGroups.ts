import { useCallback, useEffect, useState } from "react";

const KEY = "ee-nav-folded";

/** Which sidebar groups are folded, remembered on this computer. */
export function useFoldedGroups(): [Set<string>, (group: string) => void] {
  const [folded, setFolded] = useState<Set<string>>(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem(KEY) ?? "[]") as string[]);
    } catch {
      return new Set();
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify([...folded]));
    } catch {
      // Private window: folding just will not be remembered.
    }
  }, [folded]);
  const toggle = useCallback((group: string) => {
    setFolded((prev) => {
      const next = new Set(prev);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });
  }, []);
  return [folded, toggle];
}
