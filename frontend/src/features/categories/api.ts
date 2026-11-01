import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../api/queryKeys";
import type { Category } from "../../api/types";

/**
 * Unpaginated by contract — the category list is small and is only ever used
 * to fill a dropdown, on both the inventory and the products screen.
 */
export function useCategories() {
  return useQuery({
    meta: { silent: true },
    queryKey: queryKeys.categories.list,
    queryFn: ({ signal }) => api.get<Category[]>("/categories", undefined, signal),
    staleTime: 5 * 60_000,
  });
}
