import { Modal } from "../../../components/ui/Modal";
import { Button } from "../../../components/ui/Button";
import { errorCardCls } from "../../../components/ui/styles";
import { isApiError } from "../../../api/client";
import { errorMessage } from "../../../lib/errors";
import { useToast } from "../../../components/ui/toast-context";
import { useDeleteCustomer } from "../api";
import type { Customer } from "../../../api/types";

export function DeleteCustomerDialog({
  customer,
  onClose,
}: {
  customer: Customer | null;
  onClose: () => void;
}) {
  const toast = useToast();
  const remove = useDeleteCustomer();

  // Nothing references a customer yet, so the server never refuses today.
  // The branch stays because the first module that does — orders, challans —
  // will, and a refusal is a message to render in place, not a failure to
  // explain away. The server's own message says what still points here.
  const blocked = isApiError(remove.error) && remove.error.status === 409;

  function close() {
    remove.reset();
    onClose();
  }

  if (!customer) return null;

  return (
    <Modal
      open
      onClose={close}
      title="Deactivate customer"
      description={customer.name}
      footer={
        <>
          <Button onClick={close}>{blocked ? "Close" : "Cancel"}</Button>
          {blocked ? null : (
            <Button
              variant="danger"
              loading={remove.isPending}
              onClick={() =>
                remove.mutate(customer.id, {
                  onSuccess: () => {
                    toast.success(customer.name + " deactivated.");
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
          <p className="text-[13px] font-medium text-red">This customer is still in use</p>
          <p className="mt-0.5 text-[13px] text-ink-2">{errorMessage(remove.error)}</p>
          <p className="mt-2 text-[13px] text-ink-2">
            Records raised for {customer.name} still point at it. Clear or reassign those
            first, then deactivate.
          </p>
        </div>
      ) : (
        <div className="space-y-3 text-[13px] text-ink-2">
          <p>
            {customer.name} will be marked inactive and will stop appearing in customer
            dropdowns. Nothing is deleted, and any record already raised for it keeps
            pointing at it.
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
