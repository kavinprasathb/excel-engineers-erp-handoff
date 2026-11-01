import { useState } from "react";
import { PageBody } from "../../components/layout/PageHeader";
import { Icon } from "../../components/ui/Icon";
import { cardCls, gutterCls, pageHeadingCls } from "../../components/ui/styles";
import { useListParams } from "../../lib/useListParams";
import { useInventory } from "./api";
import { inventoryListParams } from "./filterKeys";
import { InventorySummaryCards } from "./components/InventorySummaryCards";
import { InventoryFilters } from "./components/InventoryFilters";
import { InventoryTable } from "./components/InventoryTable";
import { InventoryQuickView } from "./components/InventoryQuickView";
import { AdjustStockModal } from "./components/AdjustStockModal";
import { MovementsModal } from "./components/MovementsModal";
import type { InventoryRow } from "../../api/types";

/**
 * The daily screen. Composition only: the filters own the query string, each
 * child owns its own query, and the page holds nothing but which row a modal
 * is open for and which row the quick view shows.
 */
export default function InventoryPage() {
  const params = useListParams();
  const [adjusting, setAdjusting] = useState<InventoryRow | null>(null);
  const [viewingHistory, setViewingHistory] = useState<InventoryRow | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // Same key as the table's query, so this is served from the same request.
  const inventory = useInventory(inventoryListParams(params));
  const items = inventory.data?.items ?? [];
  const selected = items.find((r) => r.product_id === selectedId) ?? items[0] ?? null;

  const missingSupplier = params.get("has_supplier") === "false";

  return (
    <>
      <header className={`pt-5 pb-1 sm:pt-7 ${gutterCls}`}>
        <div className="flex items-center gap-3.5">
          <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-brand/12 text-brand ring-1 ring-brand/15">
            <Icon name="inventory" size={24} />
          </span>
          <div className="min-w-0">
            <h1 className={pageHeadingCls}>Inventory</h1>
            <p className="mt-1 text-[13.5px] text-ink-2">
              Manage your stock, track availability and keep your business running smoothly.
            </p>
          </div>
        </div>
      </header>
      <PageBody>
        <InventorySummaryCards
          missingSupplierActive={missingSupplier}
          onShowMissingSupplier={() =>
            params.set({ has_supplier: missingSupplier ? null : "false", supplier_id: null })
          }
        />
        <div className="xl:grid xl:grid-cols-[minmax(0,1fr)_300px] xl:items-start xl:gap-4">
          <div className={`min-w-0 p-3 sm:p-4 ${cardCls}`}>
            <InventoryFilters params={params} />
            <InventoryTable
              params={params}
              onAdjust={setAdjusting}
              onHistory={setViewingHistory}
              selectedId={selected?.product_id ?? null}
              onSelect={(row) => setSelectedId(row.product_id)}
            />
          </div>
          <div className="hidden xl:block">
            <InventoryQuickView row={selected} onHistory={setViewingHistory} />
          </div>
        </div>
      </PageBody>

      <AdjustStockModal row={adjusting} onClose={() => setAdjusting(null)} />
      <MovementsModal row={viewingHistory} onClose={() => setViewingHistory(null)} />
    </>
  );
}
