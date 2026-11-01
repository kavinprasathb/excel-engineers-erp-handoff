/**
 * Theme preference. The initial application happens in a blocking script in
 * index.html so there is no flash; this module only handles later changes.
 */

export type ThemePref = "light" | "dark" | "system";

import { useEffect, useState } from "react";

const KEY = "ee-theme";
/** Fired on window whenever the preference changes in this tab. */
const EVENT = "ee-theme-change";

export function getThemePref(): ThemePref {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(pref: ThemePref): void {
  const dark =
    pref === "dark" ||
    (pref === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  document.documentElement.style.colorScheme = dark ? "dark" : "light";
}

export function setThemePref(pref: ThemePref): void {
  try {
    localStorage.setItem(KEY, pref);
  } catch {
    // Private browsing: the choice just will not persist.
  }
  applyTheme(pref);
  window.dispatchEvent(new Event(EVENT));
}

/** Re-apply on OS change, but only while the preference is "system". */
export function watchSystemTheme(): () => void {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const onChange = () => {
    if (getThemePref() === "system") applyTheme("system");
  };
  mq.addEventListener("change", onChange);
  return () => mq.removeEventListener("change", onChange);
}

/** The theme actually showing, after "system" is resolved. */
export function getResolvedTheme(): "light" | "dark" {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

/**
 * One source of truth for every theme control (Settings, the top-bar toggle):
 * all of them re-read localStorage when any of them changes it, in this tab
 * (custom event) or another (storage event).
 */
export function useTheme() {
  const [pref, setPref] = useState<ThemePref>(() => getThemePref());
  const [resolved, setResolved] = useState<"light" | "dark">(() => getResolvedTheme());

  useEffect(() => {
    const sync = () => {
      setPref(getThemePref());
      setResolved(getResolvedTheme());
    };
    const onStorage = (e: StorageEvent) => {
      if (e.key !== null && e.key !== KEY) return;
      applyTheme(getThemePref());
      sync();
    };
    window.addEventListener(EVENT, sync);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(EVENT, sync);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  return { pref, resolved, setPref: setThemePref };
}
