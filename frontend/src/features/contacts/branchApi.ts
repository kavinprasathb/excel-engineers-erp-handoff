import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../api/queryKeys";
import type {
  Customer,
  CustomerBranchInput,
  Supplier,
  SupplierBranchInput,
} from "../../api/types";

export type PartyKind = "customers" | "suppliers";
type Party<K extends PartyKind> = K extends "customers" ? Customer : Supplier;
type BranchInput<K extends PartyKind> = K extends "customers"
  ? CustomerBranchInput
  : SupplierBranchInput;

/**
 * One customer or supplier with its branches. The quotation and purchase
 * order screens read this to offer the branches and show the GST number and
 * address that will print.
 */
export function useParty<K extends PartyKind>(kind: K, id: number | null) {
  return useQuery({
    meta: { silent: true },
    enabled: id !== null,
    queryKey: queryKeys[kind].detail(id ?? 0),
    queryFn: ({ signal }) => api.get<Party<K>>(`/${kind}/${id}`, undefined, signal),
  });
}

/** Add, edit and remove branches. Each answers with the parent and all its branches. */
export function useBranchMutations<K extends PartyKind>(kind: K, parentId: number) {
  const client = useQueryClient();
  const invalidate = () => client.invalidateQueries({ queryKey: queryKeys[kind].all });
  const create = useMutation({
    meta: { silent: true },
    mutationFn: (input: BranchInput<K>) => api.post<Party<K>>(`/${kind}/${parentId}/branches`, input),
    onSuccess: invalidate,
  });
  const update = useMutation({
    meta: { silent: true },
    mutationFn: ({ id, patch }: { id: number; patch: BranchInput<K> }) =>
      api.patch<Party<K>>(`/${kind}/${parentId}/branches/${id}`, patch),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    meta: { silent: true },
    mutationFn: (id: number) => api.del<void>(`/${kind}/${parentId}/branches/${id}`),
    onSuccess: invalidate,
  });
  return { create, update, remove };
}
