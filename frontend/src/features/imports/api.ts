import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../api/queryKeys";
import type { ImportJob, ImportStatus } from "../../api/types";

/** `completed` and `failed` are the two states the job never leaves. */
export function isTerminal(status: ImportStatus | undefined): boolean {
  return status === "completed" || status === "failed";
}

export function useStartImport() {
  return useMutation({
    meta: { silent: true },
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.upload<ImportJob>("/imports/products", form);
    },
  });
}

/**
 * Polls once a second and stops itself the moment the job reaches a terminal
 * status. Deriving that from the cached data rather than from a piece of
 * component state means the interval cannot outlive the dialog's own idea of
 * whether the import is still running.
 */
export function useImportJob(id: string | null) {
  return useQuery({
    meta: { silent: true },
    enabled: id !== null,
    queryKey: queryKeys.imports.detail(id ?? ""),
    queryFn: ({ signal }) => api.get<ImportJob>(`/imports/${id}`, undefined, signal),
    refetchInterval: (query) => (isTerminal(query.state.data?.status) ? false : 1000),
    // A running job is never fresh; the interval is the only cadence we want.
    staleTime: 0,
  });
}

/** Served by the API, so a plain link is the whole feature. */
export const IMPORT_TEMPLATE_URL = "/api/imports/template.xlsx";
