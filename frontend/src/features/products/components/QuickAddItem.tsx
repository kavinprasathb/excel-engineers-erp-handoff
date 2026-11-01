import { useState } from "react";
import type { FormEvent } from "react";
import { Button } from "../../../components/ui/Button";
import { Input } from "../../../components/ui/Input";
import { Select } from "../../../components/ui/Select";
import { errorMessage } from "../../../lib/errors";
import { useIsOwner } from "../../auth/api";
import { useSupplierOptions } from "../../suppliers/api";
import { useCreateProduct } from "../api";
import { STOCK_TYPES } from "../../../api/types";
import type { ProductLookup, StockType } from "../../../api/types";

/**
 * Add an item that is not in Inventory yet, without leaving the quotation.
 *
 * It is saved as a product with 0 stock (a "To order" item by default) and
 * handed back in the picker's shape, so the line is linked to it exactly as
 * if it had been picked from the catalogue. The SKU is given by the server
 * (ORD-0001...). Stock never moves here: a to-order item comes in through
 * the purchase order its order drafts.
 */
export function QuickAddItem({
  initialName,
  onAdded,
  onCancel,
}: {
  initialName: string;
  onAdded: (item: ProductLookup) => void;
  onCancel: () => void;
}) {
  const owner = useIsOwner();
  const suppliers = useSupplierOptions();
  const create = useCreateProduct();
  const [name, setName] = useState(initialName);
  const [model, setModel] = useState("");
  const [unit, setUnit] = useState("Each");
  const [hsn, setHsn] = useState("");
  const [cost, setCost] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const [type, setType] = useState<StockType>("to_order");
  const [error, setError] = useState<string | null>(null);

  function submit(e: FormEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!name.trim()) {
      setError("Enter the item name.");
      return;
    }
    const paise = Math.round(Number((cost || "0").replace(/,/g, "")) * 100);
    if (!Number.isFinite(paise) || paise < 0) {
      setError("Purchase cost must be a number in rupees.");
      return;
    }
    setError(null);
    create.mutate(
      {
        sku: "",
        name: name.trim(),
        model_number: model.trim(),
        description: "",
        unit: unit.trim() || "Each",
        hsn_code: hsn.trim(),
        purchase_cost: paise,
        sell_price: 0,
        gst_rate_bp: 1800,
        supplier_id: supplierId ? Number(supplierId) : null,
        category_id: null,
        opening_quantity: 0,
        stock_type: type,
      },
      {
        onSuccess: (p) =>
          onAdded({
            id: p.id,
            sku: p.sku,
            name: p.name,
            model_number: p.model_number,
            unit: p.unit,
            hsn_code: p.hsn_code,
            sell_price: p.sell_price,
            quantity_available: 0,
            stock_type: p.stock_type,
          }),
        onError: (err) => setError(errorMessage(err)),
      },
    );
  }

  const caption = "mb-1 block text-[12px] text-ink-2";
  return (
    <form
      aria-label="Add a new item"
      onSubmit={submit}
      className="mt-2 rounded-md border border-dashed border-brand bg-hoverfill p-3"
    >
      <p className="mb-2 text-[13px] font-medium text-ink">
        New item: saved to Inventory with 0 stock and added to this quote.
      </p>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <label className="block">
          <span className={caption}>Item name *</span>
          <Input aria-label="New item name" value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="block">
          <span className={caption}>Model / details</span>
          <Input aria-label="New item model" value={model} onChange={(e) => setModel(e.target.value)} />
        </label>
        <label className="block">
          <span className={caption}>Type</span>
          <Select aria-label="New item type" value={type} onChange={(e) => setType(e.target.value as StockType)}>
            {STOCK_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </Select>
        </label>
        <label className="block">
          <span className={caption}>Supplier</span>
          <Select aria-label="New item supplier" value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
            <option value="">No supplier</option>
            {(suppliers.data ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </label>
        <label className="block">
          <span className={caption}>Unit</span>
          <Input aria-label="New item unit" value={unit} onChange={(e) => setUnit(e.target.value)} />
        </label>
        <label className="block">
          <span className={caption}>HSN</span>
          <Input aria-label="New item HSN" inputMode="numeric" value={hsn} onChange={(e) => setHsn(e.target.value)} />
        </label>
        {owner ? (
          <label className="block">
            <span className={caption}>Purchase cost (₹, optional)</span>
            <Input
              aria-label="New item purchase cost"
              inputMode="decimal"
              placeholder="For the margin"
              value={cost}
              onChange={(e) => setCost(e.target.value)}
            />
          </label>
        ) : null}
        <div className="flex items-end gap-2">
          <Button type="submit" variant="primary" disabled={create.isPending}>
            {create.isPending ? "Saving…" : "Save & add"}
          </Button>
          <Button onClick={onCancel}>Cancel</Button>
        </div>
      </div>
      {error ? (
        <p role="alert" className="mt-2 text-[12px] text-red">
          {error}
        </p>
      ) : null}
    </form>
  );
}
