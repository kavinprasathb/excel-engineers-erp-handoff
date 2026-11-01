import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../api/queryKeys";
import type { ListParams } from "../../api/queryKeys";
import type {
  ItemSuggestion,
  Page,
  ProductLookup,
  Quotation,
  QuotationChange,
  QuotationCompare,
  QuotationCreate,
  QuotationDashboard,
  QuotationLineChange,
  QuotationPatch,
  QuotationStatus,
  QuotationSummary,
  VersionKind,
} from "../../api/types";

export function useQuotations(params: ListParams) {
  return useQuery({
    meta: { silent: true },
    queryKey: queryKeys.quotations.list(params),
    queryFn: ({ signal }) => api.get<Page<QuotationSummary>>("/quotations", { ...params }, signal),
  });
}

export function useQuotation(id: number | null) {
  return useQuery({
    meta: { silent: true },
    enabled: id !== null,
    queryKey: queryKeys.quotations.detail(id ?? 0),
    queryFn: ({ signal }) => api.get<Quotation>(`/quotations/${id}`, undefined, signal),
  });
}

/** Every revision of the same number, oldest first. */
export function useQuotationRevisions(id: number, enabled = true) {
  return useQuery({
    meta: { silent: true },
    enabled,
    queryKey: queryKeys.quotations.revisions(id),
    queryFn: ({ signal }) =>
      api.get<QuotationSummary[]>(`/quotations/${id}/revisions`, undefined, signal),
  });
}

/** What this negotiation changed against the version it was copied from. */
export function useQuotationChanges(id: number, enabled = true) {
  return useQuery({
    meta: { silent: true },
    enabled,
    queryKey: queryKeys.quotations.changes(id),
    queryFn: ({ signal }) =>
      api.get<QuotationChange[]>(`/quotations/${id}/changes`, undefined, signal),
  });
}

/** Item-by-item old and new rate, for the negotiation table. */
export function useQuotationLineChanges(id: number, enabled = true) {
  return useQuery({
    meta: { silent: true },
    enabled,
    queryKey: queryKeys.quotations.lineChanges(id),
    queryFn: ({ signal }) =>
      api.get<QuotationLineChange[]>(`/quotations/${id}/line-changes`, undefined, signal),
  });
}

/** Any two versions of one number: what changed from `against` to `id`. */
export function useQuotationCompare(id: number | null, against: number | null) {
  return useQuery({
    meta: { silent: true },
    enabled: id !== null && against !== null && id !== against,
    queryKey: queryKeys.quotations.compare(id ?? 0, against ?? 0),
    queryFn: ({ signal }) =>
      api.get<QuotationCompare>(`/quotations/${id}/compare`, { against: against ?? 0 }, signal),
  });
}

export function useQuotationDashboard() {
  return useQuery({
    meta: { silent: true },
    queryKey: queryKeys.quotations.dashboard,
    queryFn: ({ signal }) => api.get<QuotationDashboard>("/quotations/dashboard", undefined, signal),
  });
}

/** Type-ahead against the catalogue. Disabled until there is something to search. */
export function useProductLookup(q: string) {
  return useQuery({
    meta: { silent: true },
    enabled: q.trim().length > 0,
    queryKey: queryKeys.productLookup(q),
    queryFn: ({ signal }) => api.get<ProductLookup[]>("/products/lookup", { q }, signal),
    staleTime: 60_000,
  });
}

/** What was quoted before, for the description box (past letters and the app). */
export function useItemSuggestions(q: string, customerId: number | null) {
  return useQuery({
    meta: { silent: true },
    enabled: q.trim().length >= 3,
    queryKey: queryKeys.itemSuggestions(q.trim(), customerId),
    queryFn: ({ signal }) =>
      api.get<ItemSuggestion[]>(
        "/quotations/item-suggestions",
        { q: q.trim(), ...(customerId ? { customer_id: customerId } : {}) },
        signal,
      ),
    staleTime: 60_000,
  });
}

function useQuotationInvalidation() {
  const client = useQueryClient();
  return (q?: Quotation) => {
    client.invalidateQueries({ queryKey: queryKeys.quotations.all });
    if (q) client.setQueryData(queryKeys.quotations.detail(q.id), q);
  };
}

export function useCreateQuotation() {
  const done = useQuotationInvalidation();
  return useMutation({
    meta: { silent: true },
    mutationFn: (input: QuotationCreate) => api.post<Quotation>("/quotations", input),
    onSuccess: done,
  });
}

export function useUpdateQuotation() {
  const done = useQuotationInvalidation();
  return useMutation({
    meta: { silent: true },
    mutationFn: ({ id, patch }: { id: number; patch: QuotationPatch }) =>
      api.patch<Quotation>(`/quotations/${id}`, patch),
    onSuccess: done,
  });
}

/** whole: the number with all its negotiations; otherwise just this negotiation. */
export function useDeleteQuotation() {
  const done = useQuotationInvalidation();
  return useMutation({
    meta: { silent: true },
    mutationFn: ({ id, whole }: { id: number; whole: boolean }) =>
      api.del<undefined>(`/quotations/${id}?whole=${whole}`),
    onSuccess: done,
  });
}

export function useReviseQuotation() {
  const done = useQuotationInvalidation();
  return useMutation({
    meta: { silent: true },
    // A revised quotation (R) for product or technical changes; a negotiation
    // (N) for price only.
    mutationFn: ({ id, kind }: { id: number; kind: VersionKind }) =>
      api.post<Quotation>(`/quotations/${id}/revise`, { kind }),
    onSuccess: done,
  });
}

export function useSetQuotationStatus() {
  const done = useQuotationInvalidation();
  return useMutation({
    meta: { silent: true },
    mutationFn: ({ id, status, reason = "" }: { id: number; status: QuotationStatus; reason?: string }) =>
      api.post<Quotation>(`/quotations/${id}/status`, { status, reason }),
    onSuccess: done,
  });
}

/** The PDF is served on the session cookie, so a plain navigation is enough. */
export function quotationPdfUrl(id: number): string {
  return `/api/quotations/${id}/pdf`;
}
