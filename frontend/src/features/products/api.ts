import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../api/queryKeys";
import type { ListParams } from "../../api/queryKeys";
import type { Page, Product, StockType } from "../../api/types";

/**
 * The write shape. Relations go over the wire as ids while the read shape
 * returns `{id, name}` objects, so the two are deliberately not the same type.
 */
export interface ProductInput {
  sku: string;
  name: string;
  model_number: string;
  description: string;
  unit: string;
  hsn_code: string;
  /** Integer paise. */
  purchase_cost: number | null;
  /** Integer paise. */
  sell_price: number;
  gst_rate_bp: number;
  supplier_id: number | null;
  category_id: number | null;
  /** Omitted on create: stocked. */
  stock_type?: StockType;
}

/** Only on create: PATCH never touches stock, per the contract. */
export interface ProductCreateInput extends ProductInput {
  opening_quantity: number;
}

export function useProducts(params: ListParams) {
  return useQuery({
    meta: { silent: true },
    queryKey: queryKeys.products.list(params),
    queryFn: ({ signal }) => api.get<Page<Product>>("/products", { ...params }, signal),
  });
}

/**
 * A product write moves stock counts and the missing-supplier tally with it,
 * so inventory is always invalidated alongside.
 */
function useProductInvalidation() {
  const client = useQueryClient();
  return () => {
    client.invalidateQueries({ queryKey: queryKeys.products.all });
    client.invalidateQueries({ queryKey: queryKeys.inventory.all });
    client.invalidateQueries({ queryKey: queryKeys.suppliers.all });
  };
}

export function useCreateProduct() {
  const invalidate = useProductInvalidation();
  return useMutation({
    meta: { silent: true },
    mutationFn: (input: ProductCreateInput) => api.post<Product>("/products", input),
    onSuccess: invalidate,
  });
}

export function useUpdateProduct() {
  const invalidate = useProductInvalidation();
  return useMutation({
    meta: { silent: true },
    mutationFn: ({ id, patch }: { id: number; patch: Partial<ProductInput> }) =>
      api.patch<Product>(`/products/${id}`, patch),
    onSuccess: invalidate,
  });
}

export function useDeleteProduct() {
  const invalidate = useProductInvalidation();
  return useMutation({
    meta: { silent: true },
    mutationFn: (id: number) => api.del<void>(`/products/${id}`),
    onSuccess: invalidate,
  });
}

/**
 * Purchase cost by product, for the margin hint in the quote editor. Owner
 * only: for staff the server sends null, so nothing is fetched at all.
 */
export function useProductCosts(ids: number[], enabled: boolean): Map<number, number | null> {
  const unique = [...new Set(ids)];
  const results = useQueries({
    queries: unique.map((id) => ({
      queryKey: queryKeys.products.detail(id),
      queryFn: ({ signal }: { signal: AbortSignal }) => api.get<Product>(`/products/${id}`, undefined, signal),
      enabled,
      staleTime: 60_000,
      meta: { silent: true },
    })),
  });
  const out = new Map<number, number | null>();
  results.forEach((r, i) => out.set(unique[i], r.data?.purchase_cost ?? null));
  return out;
}
