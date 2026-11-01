import { useState } from "react";
import type { FormEvent } from "react";
import { Drawer } from "../../../components/ui/Drawer";
import { Button } from "../../../components/ui/Button";
import { FormField } from "../../../components/ui/FormField";
import { Input } from "../../../components/ui/Input";
import { Select } from "../../../components/ui/Select";
import { Textarea } from "../../../components/ui/Textarea";
import { errorCardCls } from "../../../components/ui/styles";
import { errorMessage } from "../../../lib/errors";
import { useToast } from "../../../components/ui/toast-context";
import {
  bpToPercent,
  paiseToRupeeInput,
  percentToBp,
  rupeeInputToPaise,
} from "../../../lib/format";
import { useSupplierOptions } from "../../suppliers/api";
import { useCategories } from "../../categories/api";
import { useSettings } from "../../settings/api";
import { useCreateProduct, useUpdateProduct } from "../api";
import type { ProductInput } from "../api";
import { STOCK_TYPES } from "../../../api/types";
import type { Product, StockType } from "../../../api/types";
import { useIsOwner } from "../../auth/api";

/**
 * Money and GST are edited in the units a person uses — rupees and percent —
 * and converted to paise and basis points on submit only. Holding paise in the
 * field would mean the user types 425000 for four thousand two hundred and
 * fifty rupees, which is how a price ends up a hundred times wrong.
 */
interface FormState {
  sku: string;
  name: string;
  model_number: string;
  description: string;
  unit: string;
  hsn_code: string;
  purchase_cost: string;
  sell_price: string;
  gst_percent: string;
  supplier_id: string;
  category_id: string;
  opening_quantity: string;
  stock_type: StockType;
}

const BLANK: FormState = {
  sku: "",
  name: "",
  model_number: "",
  description: "",
  unit: "piece",
  hsn_code: "",
  purchase_cost: "0.00",
  sell_price: "0.00",
  gst_percent: "18",
  supplier_id: "",
  category_id: "",
  opening_quantity: "0",
  stock_type: "stocked",
};

function toForm(product: Product): FormState {
  return {
    sku: product.sku,
    name: product.name,
    model_number: product.model_number,
    description: product.description,
    unit: product.unit,
    hsn_code: product.hsn_code,
    purchase_cost: paiseToRupeeInput(product.purchase_cost ?? 0),
    sell_price: paiseToRupeeInput(product.sell_price),
    gst_percent: String(bpToPercent(product.gst_rate_bp)),
    supplier_id: product.supplier ? String(product.supplier.id) : "",
    category_id: product.category ? String(product.category.id) : "",
    opening_quantity: "0",
    stock_type: product.stock_type ?? "stocked",
  };
}

type Errors = Partial<Record<keyof FormState, string>>;

export function ProductFormDrawer({
  open,
  product,
  onClose,
}: {
  open: boolean;
  /** null means "create". */
  product: Product | null;
  onClose: () => void;
}) {
  const owner = useIsOwner();
  const toast = useToast();
  const suppliers = useSupplierOptions(open);
  const categories = useCategories();
  const settings = useSettings();
  const create = useCreateProduct();
  const update = useUpdateProduct();

  const pending = create.isPending || update.isPending;
  const saveError = create.error ?? update.error;

  const [form, setForm] = useState<FormState>(BLANK);
  const [errors, setErrors] = useState<Errors>({});

  const identity = open ? (product?.id ?? "new") : null;
  const [seeded, setSeeded] = useState<number | "new" | null>(null);
  if (identity !== seeded) {
    setSeeded(identity);
    setErrors({});
    create.reset();
    update.reset();
    if (product) {
      setForm(toForm(product));
    } else {
      // A new product inherits the company's default GST rather than a
      // hard-coded 18% that quietly disagrees with Settings.
      setForm({
        ...BLANK,
        gst_percent: settings.data
          ? String(bpToPercent(settings.data.default_gst_rate_bp))
          : BLANK.gst_percent,
      });
    }
  }

  function field(key: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function validate(): Errors {
    const e: Errors = {};
    if (!form.sku.trim()) e.sku = "Enter a SKU.";
    if (!form.name.trim()) e.name = "Enter a product name.";
    if (!form.unit.trim()) e.unit = "Enter a unit, e.g. piece.";

    for (const key of ["purchase_cost", "sell_price"] as const) {
      const n = Number(form[key]);
      if (!Number.isFinite(n) || n < 0) e[key] = "Enter an amount in rupees, 0 or more.";
    }

    const gst = Number(form.gst_percent);
    if (!Number.isFinite(gst) || gst < 0 || gst > 100) {
      e.gst_percent = "Enter a percentage between 0 and 100.";
    }

    if (!product) {
      const q = Number(form.opening_quantity);
      if (!Number.isInteger(q) || q < 0) {
        e.opening_quantity = "Enter a whole number, 0 or more.";
      }
    }
    return e;
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    const base: ProductInput = {
      sku: form.sku.trim(),
      name: form.name.trim(),
      model_number: form.model_number.trim(),
      description: form.description,
      unit: form.unit.trim(),
      hsn_code: form.hsn_code.trim(),
      purchase_cost: rupeeInputToPaise(form.purchase_cost),
      sell_price: rupeeInputToPaise(form.sell_price),
      gst_rate_bp: percentToBp(Number(form.gst_percent)),
      supplier_id: form.supplier_id === "" ? null : Number(form.supplier_id),
      category_id: form.category_id === "" ? null : Number(form.category_id),
      stock_type: form.stock_type,
    };

    const done = {
      onSuccess: () => {
        toast.success(product ? "Product updated." : "Product added.");
        onClose();
      },
    };

    if (product) update.mutate({ id: product.id, patch: base }, done);
    else create.mutate({ ...base, opening_quantity: Number(form.opening_quantity) }, done);
  }

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={product ? "Edit product" : "New product"}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form="product-form" variant="primary" loading={pending}>
            {product ? "Save changes" : "Add product"}
          </Button>
        </>
      }
    >
      <form id="product-form" onSubmit={onSubmit} noValidate className="space-y-4">
        <FormField label="SKU" required error={errors.sku}>
          {(props) => (
            <Input
              {...props}
              value={form.sku}
              onChange={(e) => field("sku", e.target.value.toUpperCase())}
            />
          )}
        </FormField>

        <FormField label="Name" required error={errors.name}>
          {(props) => (
            <Input {...props} value={form.name} onChange={(e) => field("name", e.target.value)} />
          )}
        </FormField>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Model number">
            {(props) => (
              <Input
                {...props}
                value={form.model_number}
                onChange={(e) => field("model_number", e.target.value)}
              />
            )}
          </FormField>
          <FormField label="Unit" required error={errors.unit}>
            {(props) => (
              <Input
                {...props}
                value={form.unit}
                onChange={(e) => field("unit", e.target.value)}
              />
            )}
          </FormField>
        </div>

        <FormField
          label="Type"
          hint="Stocked: kept on the shelf. To order: bought in when an order needs it. Service: never stocked."
        >
          {(props) => (
            <Select
              {...props}
              value={form.stock_type}
              onChange={(e) => field("stock_type", e.target.value as StockType)}
            >
              {STOCK_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          )}
        </FormField>

        <FormField label="Supplier" hint="Products without a supplier are flagged on Inventory.">
          {(props) => (
            <Select
              {...props}
              value={form.supplier_id}
              onChange={(e) => field("supplier_id", e.target.value)}
            >
              <option value="">No supplier</option>
              {(suppliers.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          )}
        </FormField>

        <FormField label="Category">
          {(props) => (
            <Select
              {...props}
              value={form.category_id}
              onChange={(e) => field("category_id", e.target.value)}
            >
              <option value="">No category</option>
              {(categories.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          )}
        </FormField>

        <div className="grid gap-4 sm:grid-cols-2">
          {owner ? (
          <FormField label="Purchase cost (₹)" error={errors.purchase_cost}>
            {(props) => (
              <Input
                {...props}
                type="number"
                inputMode="decimal"
                min={0}
                step="0.01"
                className="tabular-nums"
                value={form.purchase_cost}
                onChange={(e) => field("purchase_cost", e.target.value)}
              />
            )}
          </FormField>
          ) : null}
          <FormField label="Sell price (₹)" error={errors.sell_price}>
            {(props) => (
              <Input
                {...props}
                type="number"
                inputMode="decimal"
                min={0}
                step="0.01"
                className="tabular-nums"
                value={form.sell_price}
                onChange={(e) => field("sell_price", e.target.value)}
              />
            )}
          </FormField>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="GST rate (%)" error={errors.gst_percent}>
            {(props) => (
              <Input
                {...props}
                type="number"
                inputMode="decimal"
                min={0}
                max={100}
                step="0.01"
                className="tabular-nums"
                value={form.gst_percent}
                onChange={(e) => field("gst_percent", e.target.value)}
              />
            )}
          </FormField>
          <FormField label="HSN code">
            {(props) => (
              <Input
                {...props}
                inputMode="numeric"
                value={form.hsn_code}
                onChange={(e) => field("hsn_code", e.target.value)}
              />
            )}
          </FormField>
        </div>

        {product ? null : (
          <FormField
            label="Opening quantity"
            error={errors.opening_quantity}
            hint="Recorded as the first stock movement. Editing a product never changes stock."
          >
            {(props) => (
              <Input
                {...props}
                type="number"
                inputMode="numeric"
                min={0}
                step={1}
                className="tabular-nums"
                value={form.opening_quantity}
                onChange={(e) => field("opening_quantity", e.target.value)}
              />
            )}
          </FormField>
        )}

        <FormField label="Description">
          {(props) => (
            <Textarea
              {...props}
              value={form.description}
              onChange={(e) => field("description", e.target.value)}
            />
          )}
        </FormField>

        {saveError ? (
          <div className={errorCardCls} role="alert">
            <p className="text-[13px] font-medium text-red">Could not save this product</p>
            <p className="mt-0.5 text-[13px] text-ink-2">{errorMessage(saveError)}</p>
          </div>
        ) : null}
      </form>
    </Drawer>
  );
}
