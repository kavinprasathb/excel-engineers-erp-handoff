import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../api/queryKeys";
import type { Settings, SettingsPatch } from "../../api/types";

/** Singleton resource — no id in the path, and one cache entry. */
export function useSettings() {
  return useQuery({
    queryKey: queryKeys.settings,
    queryFn: () => api.get<Settings>("/settings"),
  });
}

export function useUpdateSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (patch: SettingsPatch) => api.patch<Settings>("/settings", patch),
    meta: { silent: true },
    onSuccess: (settings) => {
      // The response is the full resource, so seed rather than refetch.
      client.setQueryData(queryKeys.settings, settings);
      // The low-stock threshold changes what the server flags, so anything
      // carrying is_low_stock is now wrong.
      client.invalidateQueries({ queryKey: queryKeys.inventory.all });
    },
  });
}
