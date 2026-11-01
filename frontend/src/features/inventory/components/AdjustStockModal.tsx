import { useState } from "react";
import type { FormEvent } from "react";
import { Modal } from "../../../components/ui/Modal";
import { Button } from "../../../components/ui/Button";
import { FormField } from "../../../components/ui/FormField";
import { Input } from "../../../components/ui/Input";
import { Textarea } from "../../../components/ui/Textarea";
import { SegmentedControl } from "../../../components/ui/SegmentedControl";
import { errorCardCls } from "../../../components/ui/styles";
import { Icon } from "../../../components/ui/Icon";
import { errorMessage } from "../../../lib/errors";
import { formatNumber } from "../../../lib/format";
import { useAdjustStock } from "../api";
import type { InventoryRow } from "../../../api/types";

type Direction = "add" | "remove";

const DIRECTIONS = [
  { value: "add" as const, label: "Add stock" },
  { value: "remove" as const, label: "Remove stock" },
];

/**
 * The signed delta is composed here, not typed by the user.
 *
 * Asking for "-5" invites a missing minus sign, and a missing minus sign on
 * this screen adds five pumps that do not exist. A direction plus a positive
 * quantity cannot be mistyped into its own opposite.
 */
export function AdjustStockModal({
  row,
  onClose,
}: {
  row: InventoryRow | null;
  onClose: () => void;
}) {
  const adjust = useAdjustStock();
  const [direction, setDirection] = useState<Direction>("add");
  const [quantity, setQuantity] = useState("");
  const [note, setNote] = useState("");
  const [fieldError, setFieldError] = useState<string | undefined>(undefined);
  const [result, setResult] = useState<InventoryRow | null>(null);

  function reset() {
    setDirection("add");
    setQuantity("");
    setNote("");
    setFieldError(undefined);
    setResult(null);
    adjust.reset();
  }

  function close() {
    reset();
    onClose();
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!row) return;

    const n = Number(quantity);
    if (!Number.isInteger(n) || n <= 0) {
      setFieldError("Enter a whole quantity greater than zero.");
      return;
    }
    setFieldError(undefined);

    adjust.mutate(
      { productId: row.product_id, delta: direction === "add" ? n : -n, note: note.trim() },
      { onSuccess: (updated) => setResult(updated) },
    );
  }

  if (!row) return null;

  return (
    <Modal
      open
      onClose={close}
      title="Adjust stock"
      description={`${row.name} · ${row.sku}`}
      footer={
        result ? (
          <>
            <Button onClick={reset}>Adjust again</Button>
            <Button variant="primary" onClick={close}>
              Done
            </Button>
          </>
        ) : (
          <>
            <Button onClick={close}>Cancel</Button>
            <Button
              type="submit"
              form="adjust-stock-form"
              variant="primary"
              loading={adjust.isPending}
            >
              Save adjustment
            </Button>
          </>
        )
      }
    >
      {result ? (
        <div>
          <p className="flex items-center gap-2 text-[13px] font-medium text-green">
            <Icon name="check" size={15} />
            Stock updated.
          </p>
          <dl className="mt-3 grid grid-cols-3 gap-3">
            <Figure label="On hand" value={result.quantity_on_hand} />
            <Figure label="Reserved" value={result.quantity_reserved} />
            <Figure label="Available" value={result.quantity_available} />
          </dl>
        </div>
      ) : (
        <form id="adjust-stock-form" onSubmit={onSubmit} noValidate className="space-y-4">
          <div>
            <p className="mb-1.5 text-xs font-medium text-ink-2">Direction</p>
            <SegmentedControl
              label="Direction"
              fullWidth
              value={direction}
              options={DIRECTIONS}
              onChange={setDirection}
            />
          </div>

          <FormField
            label="Quantity"
            required
            error={fieldError}
            hint={`Currently ${formatNumber(row.quantity_on_hand)} on hand, ${formatNumber(
              row.quantity_reserved,
            )} reserved.`}
          >
            {(props) => (
              <Input
                {...props}
                type="number"
                inputMode="numeric"
                min={1}
                step={1}
                className="tabular-nums"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
              />
            )}
          </FormField>

          <FormField label="Note" hint="Why the count changed. Shown in the movement history.">
            {(props) => (
              <Textarea
                {...props}
                value={note}
                placeholder="e.g. damaged in transit"
                onChange={(e) => setNote(e.target.value)}
              />
            )}
          </FormField>

          {adjust.isError ? (
            // The server refuses a removal that would eat into reserved stock.
            // That refusal is the useful part of this screen, so it is stated
            // in full rather than reduced to "failed".
            <div className={errorCardCls} role="alert">
              <p className="text-[13px] font-medium text-red">Adjustment refused</p>
              <p className="mt-0.5 text-[13px] text-ink-2">{errorMessage(adjust.error)}</p>
            </div>
          ) : null}
        </form>
      )}
    </Modal>
  );
}

function Figure({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-line p-3">
      <dt className="text-[10px] font-medium uppercase tracking-wide text-ink-2">{label}</dt>
      <dd className="mt-1 text-[15px] font-semibold tabular-nums text-ink">
        {formatNumber(value)}
      </dd>
    </div>
  );
}
