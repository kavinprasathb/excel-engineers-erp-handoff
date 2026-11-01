import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * Filters live in the query string, not in component state.
 *
 * A stock view someone is looking at ("everything low, from KSB, missing a
 * supplier") survives a refresh and can be pasted into a WhatsApp message to
 * a colleague. That is the whole reason this hook exists rather than useState.
 */
export type ParamValue = string | number | boolean | null | undefined;

export interface ListParamsApi {
  /** Raw string, `""` when absent — matching the client's "empty is absent". */
  get: (key: string) => string;
  /** Numeric param, or null when absent or unparseable. */
  getNumber: (key: string) => number | null;
  /**
   * Writes a patch. Any key set to `""`/null/undefined is removed, and the
   * page resets to 1 unless the patch itself sets a page — changing a filter
   * while sitting on page 6 would otherwise show an empty table.
   */
  set: (patch: Record<string, ParamValue>) => void;
  page: number;
  setPage: (page: number) => void;
  /** True when any filter other than the page is active. */
  hasFilters: (keys: readonly string[]) => boolean;
  clear: (keys: readonly string[]) => void;
}

export function useListParams(): ListParamsApi {
  const [params, setSearchParams] = useSearchParams();

  const get = useCallback((key: string) => params.get(key) ?? "", [params]);

  const getNumber = useCallback(
    (key: string) => {
      const raw = params.get(key);
      if (raw === null || raw === "") return null;
      const n = Number(raw);
      return Number.isFinite(n) ? n : null;
    },
    [params],
  );

  const set = useCallback(
    (patch: Record<string, ParamValue>) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [key, value] of Object.entries(patch)) {
            if (value === null || value === undefined || value === "") next.delete(key);
            else next.set(key, String(value));
          }
          if (!("page" in patch)) next.delete("page");
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const pageRaw = Number(params.get("page") ?? "1");
  const page = Number.isFinite(pageRaw) && pageRaw >= 1 ? Math.floor(pageRaw) : 1;

  const setPage = useCallback((next: number) => set({ page: next <= 1 ? null : next }), [set]);

  const hasFilters = useCallback(
    (keys: readonly string[]) => keys.some((k) => (params.get(k) ?? "") !== ""),
    [params],
  );

  const clear = useCallback(
    (keys: readonly string[]) => {
      const patch: Record<string, ParamValue> = {};
      for (const k of keys) patch[k] = null;
      set(patch);
    },
    [set],
  );

  return useMemo(
    () => ({ get, getNumber, set, page, setPage, hasFilters, clear }),
    [get, getNumber, set, page, setPage, hasFilters, clear],
  );
}
