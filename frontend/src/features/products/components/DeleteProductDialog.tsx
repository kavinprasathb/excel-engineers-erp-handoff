import { Modal } from "../../../components/ui/Modal";
import { Button } from "../../../components/ui/Button";
import { errorCardCls } from "../../../components/ui/styles";
import { errorMessage } from "../../../lib/errors";
import { formatNumber } from "../../../lib/format";
import { useToast } from "../../../components/ui/toast-context";
import { useDeleteProduct } from "../api";
import type { Product } from "../../../api/types";

/** Soft delete, and the dialog says so rather than implying data is destroyed. */
export function DeleteProductDialog({
  product,
  onClose,
}: {
  product: Product | null;
  onClose: () => void;
}) {
  const toast = useToast();
  const remove = useDeleteProduct();

  function close() {
    remove.reset();
    onClose();
  }

  if (!product) return null;

  const onHand = product.inventory.quantity_on_hand;

  return (
    <Modal
      open
      onClose={close}
      title="Deactivate product"
      description={product.name + " · " + product.sku}
      footer={
        <>
          <Button onClick={close}>Cancel</Button>
          <Button
            variant="danger"
            loading={remove.isPending}
            onClick={() =>
              remove.mutate(product.id, {
                onSuccess: () => {
                  toast.success(product.name + " deactivated.");
                  close();
                },
              })
            }
          >
            Deactivate
          </Button>
        </>
      }
    >
      <div className="space-y-3 text-[13px] text-ink-2">
        <p>
          {product.name} will be marked inactive and hidden from the active catalogue. Its
          stock record and movement history are kept.
        </p>
        {onHand > 0 ? (
          <p className="text-amber">
            It still has{" "}
            <span className="tabular-nums">{formatNumber(onHand)}</span> on hand. Deactivating
            does not write that stock off.
          </p>
        ) : null}
        {remove.isError ? (
          <div className={errorCardCls} role="alert">
            <p className="text-[13px] font-medium text-red">Could not deactivate</p>
            <p className="mt-0.5 text-[13px] text-ink-2">{errorMessage(remove.error)}</p>
          </div>
        ) : null}
      </div>
    </Modal>
  );
}
