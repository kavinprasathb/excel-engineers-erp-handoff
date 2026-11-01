import { Modal } from "../../../components/ui/Modal";
import { Button } from "../../../components/ui/Button";
import { errorCardCls } from "../../../components/ui/styles";
import { isApiError } from "../../../api/client";
import { errorMessage } from "../../../lib/errors";
import { formatNumber } from "../../../lib/format";
import { useToast } from "../../../components/ui/toast-context";
import { useDeleteSupplier } from "../api";
import type { Supplier } from "../../../api/types";

export function DeleteSupplierDialog({
  supplier,
  onClose,
}: {
  supplier: Supplier | null;
  onClose: () => void;
}) {
  const toast = useToast();
  const remove = useDeleteSupplier();

  // A 409 here is not a failure to explain away: it means real products still
  // point at this supplier, and the way out is to retag them, not to retry.
  const blocked = isApiError(remove.error) && remove.error.status === 409;

  function close() {
    remove.reset();
    onClose();
  }

  if (!supplier) return null;

  return (
    <Modal
      open
      onClose={close}
      title="Deactivate supplier"
      description={supplier.name}
      footer={
        <>
          <Button onClick={close}>{blocked ? "Close" : "Cancel"}</Button>
          {blocked ? null : (
            <Button
              variant="danger"
              loading={remove.isPending}
              onClick={() =>
                remove.mutate(supplier.id, {
                  onSuccess: () => {
                    toast.success(supplier.name + " deactivated.");
                    close();
                  },
                })
              }
            >
              Deactivate
            </Button>
          )}
        </>
      }
    >
      {blocked ? (
        <div className={errorCardCls} role="alert">
          <p className="text-[13px] font-medium text-red">This supplier is still in use</p>
          <p className="mt-0.5 text-[13px] text-ink-2">{errorMessage(remove.error)}</p>
          <p className="mt-2 text-[13px] text-ink-2">
            Move the products that reference {supplier.name} to another supplier first — the
            Products screen, filtered by this supplier, lists them.
          </p>
        </div>
      ) : (
        <div className="space-y-3 text-[13px] text-ink-2">
          <p>
            {supplier.name} will be marked inactive and will stop appearing in supplier
            dropdowns. Nothing is deleted, and past records keep pointing at it.
          </p>
          <p>
            It is currently linked to{" "}
            <span className="tabular-nums text-ink">{formatNumber(supplier.product_count)}</span>{" "}
            {supplier.product_count === 1 ? "product" : "products"}.
          </p>
          {remove.isError ? (
            <div className={errorCardCls} role="alert">
              <p className="text-[13px] font-medium text-red">Could not deactivate</p>
              <p className="mt-0.5 text-[13px] text-ink-2">{errorMessage(remove.error)}</p>
            </div>
          ) : null}
        </div>
      )}
    </Modal>
  );
}
