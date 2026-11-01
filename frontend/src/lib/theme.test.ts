import { beforeEach, describe, expect, it, vi } from "vitest";
import { applyTheme, getThemePref, setThemePref, watchSystemTheme } from "./theme";

function stubPrefersDark(dark: boolean, listeners: Array<() => void> = []) {
  window.matchMedia = ((query: string) => ({
    matches: dark,
    media: query,
    onchange: null,
    addEventListener: (_: string, fn: () => void) => {
      listeners.push(fn);
    },
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

describe("theme preference", () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.theme;
    stubPrefersDark(false);
  });

  it("defaults to system when nothing is stored", () => {
    expect(getThemePref()).toBe("system");
  });

  it("ignores a stored value that is not a real preference", () => {
    localStorage.setItem("ee-theme", "chartreuse");
    expect(getThemePref()).toBe("system");
  });

  it("persists an explicit choice and stamps the root element", () => {
    setThemePref("dark");

    expect(localStorage.getItem("ee-theme")).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
    expect(getThemePref()).toBe("dark");
  });

  it("resolves system against the OS preference", () => {
    stubPrefersDark(true);
    applyTheme("system");
    expect(document.documentElement.dataset.theme).toBe("dark");

    stubPrefersDark(false);
    applyTheme("system");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("follows an OS change only while the preference is system", () => {
    const listeners: Array<() => void> = [];
    stubPrefersDark(false, listeners);
    const stop = watchSystemTheme();

    // Explicit dark must survive the OS flipping to light.
    setThemePref("dark");
    listeners.forEach((fn) => fn());
    expect(document.documentElement.dataset.theme).toBe("dark");

    setThemePref("system");
    stubPrefersDark(true, listeners);
    listeners.forEach((fn) => fn());
    expect(document.documentElement.dataset.theme).toBe("dark");

    stop();
  });

  it("survives localStorage being unavailable", () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    expect(getThemePref()).toBe("system");
    expect(() => setThemePref("light")).not.toThrow();
    expect(document.documentElement.dataset.theme).toBe("light");

    getItem.mockRestore();
    setItem.mockRestore();
  });
});
