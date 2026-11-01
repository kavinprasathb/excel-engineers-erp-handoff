import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { Select } from "../../components/ui/Select";
import { FormField } from "../../components/ui/FormField";
import { Input } from "../../components/ui/Input";
import { Loading } from "../../components/ui/Spinner";
import { Modal } from "../../components/ui/Modal";
import { ErrorState } from "../../components/ui/ErrorState";
import { useToast } from "../../components/ui/toast-context";
import { errorMessage } from "../../lib/errors";
import { formatRupees, formatQuoteDate } from "../quotations/format";
import { useSupplierOptions } from "../suppliers/api";
import { useParty } from "../contacts/branchApi";
import { formatAddress } from "../contacts/partyRules";
import {
  purchaseOrderPdfUrl,
  useMarkPoReceived,
  useMarkPoSent,
  usePurchaseOrder,
  useSetPoSupplier,
} from "./api";
import { PoStatusBadge } from "./badges";

export default function PurchaseOrderPage() {
  const { id } = useParams();
  const poId = Number(id);
  const navigate = useNavigate();
  const toast = useToast();
  const po = usePurchaseOrder(poId);
  const suppliers = useSupplierOptions();
  const setSupplier = useSetPoSupplier();
  const markSent = useMarkPoSent();
  const markReceived = useMarkPoReceived();
  // null: nothing changed yet, show what is saved on the purchase order.
  const [picked, setPicked] = useState<{ supplier: string; branch: string } | null>(null);
  const [confirmReceive, setConfirmReceive] = useState(false);

  if (po.isPending) {
    return (
      <>
        <PageHeader title="Purchase order" />
        <PageBody>
          <Loading />
        </PageBody>
      </>
    );
  }
  if (po.isError) {
    return (
      <>
        <PageHeader title="Purchase order" />
        <PageBody>
          <ErrorState title="Could not load this purchase order" error={po.error} onRetry={() => po.refetch()} />
        </PageBody>
      </>
    );
  }
  const p = po.data;
  const current = picked ?? {
    supplier: p.supplier ? String(p.supplier.id) : "",
    branch: p.supplier_branch ? String(p.supplier_branch.id) : "",
  };
  const changed =
    picked !== null &&
    (picked.supplier !== String(p.supplier?.id ?? "") ||
      picked.branch !== String(p.supplier_branch?.id ?? ""));
  const total = p.lines.reduce((s, l) => s + l.quantity * (l.rate_paise ?? 0), 0);
  const showCost = p.lines.every((l) => l.rate_paise !== null);
  const draft = p.status === "draft";

  return (
    <>
      <PageHeader
        title={p.number}
        description={`${p.supplier ? p.supplier.name : "Supplier not set"}${p.supplier_branch ? ` (${p.supplier_branch.name})` : ""} · drafted ${formatQuoteDate(p.created_at.slice(0, 10))}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <PoStatusBadge status={p.status} />
            {p.order_id ? <Button onClick={() => navigate(`/orders/${p.order_id}`)}>Order</Button> : null}
            {showCost ? <Button onClick={() => window.open(purchaseOrderPdfUrl(p.id), "_blank")}>PDF</Button> : null}
            {draft ? (
              <Button
                variant="primary"
                disabled={!p.supplier}
                loading={markSent.isPending}
                onClick={() =>
                  markSent.mutate(p.id, {
                    onSuccess: () => toast.success(`${p.number} marked as sent.`),
                    onError: (e) => toast.error(errorMessage(e)),
                  })
                }
              >
                Mark as sent
              </Button>
            ) : null}
            {p.status !== "received" ? (
              <Button variant={draft ? "ghost" : "primary"} disabled={!p.supplier} onClick={() => setConfirmReceive(true)}>
                Mark as received
              </Button>
            ) : null}
          </div>
        }
      />
      <PageBody>
        <div className="space-y-4">
          {p.status === "received" ? (
            <p className="rounded-md border border-line bg-hoverfill px-3 py-2 text-[13px] text-ink">
              Received{p.received_at ? ` on ${formatQuoteDate(p.received_at.slice(0, 10))}` : ""}. The items
              were added to Inventory and held for the order waiting on them.
            </p>
          ) : (
            <p className="rounded-md border border-line bg-hoverfill px-3 py-2 text-[13px] text-ink">
              When the goods arrive, press <b>Mark as received</b>. They are added to Inventory,
              and the order waiting on them is updated by itself.
            </p>
          )}
          {draft ? (
            <Card>
              <CardHeader
                title="Supplier"
                description={p.supplier ? "Change it if this order should go elsewhere." : "This product has no supplier on record. Choose one to send this purchase order."}
              />
              <CardBody>
                <SupplierPicker
                  suppliers={suppliers.data ?? []}
                  value={current}
                  onChange={setPicked}
                />
                <div className="mt-3 flex justify-end">
                  <Button
                    disabled={!changed || !current.supplier}
                    loading={setSupplier.isPending}
                    onClick={() =>
                      setSupplier.mutate(
                        {
                          id: p.id,
                          supplierId: Number(current.supplier),
                          branchId: current.branch ? Number(current.branch) : null,
                        },
                        {
                          onSuccess: () => {
                            setPicked(null);
                            toast.success("Supplier saved.");
                          },
                          onError: (e) => toast.error(errorMessage(e)),
                        },
                      )
                    }
                  >
                    Save supplier
                  </Button>
                </div>
              </CardBody>
            </Card>
          ) : null}

          <Card>
            <CardHeader title="Items to buy" description="Quantity is what the order is short of; rate is the product's purchase cost." />
            <CardBody>
              <table className="w-full text-[13px]">
                <thead className="text-left text-[11px] font-medium uppercase tracking-wide text-ink-2">
                  <tr className="border-b border-line">
                    <th className="py-2 pr-3">Item</th>
                    <th className="px-3 py-2 text-right">Qty</th>
                    <th className="px-3 py-2 text-right">Rate</th>
                    <th className="px-3 py-2 text-right">GST</th>
                    <th className="py-2 pl-3 text-right">Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {p.lines.map((l) => (
                    <tr key={l.id}>
                      <td className="py-2 pr-3 text-ink">{l.description}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-ink">{l.quantity}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-ink">{l.rate_paise === null ? "—" : formatRupees(l.rate_paise)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-ink-2">{l.gst_rate_bp / 100}%</td>
                      <td className="py-2 pl-3 text-right tabular-nums text-ink">{l.rate_paise === null ? "—" : formatRupees(l.quantity * l.rate_paise)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-line">
                    <td colSpan={4} className="py-2 pr-3 text-right text-ink-2">Total before GST</td>
                    <td className="py-2 pl-3 text-right font-semibold tabular-nums text-ink">{formatRupees(total)}</td>
                  </tr>
                </tfoot>
              </table>
            </CardBody>
          </Card>
        </div>
      </PageBody>

      <Modal
        open={confirmReceive}
        onClose={() => setConfirmReceive(false)}
        title="Goods received?"
        description="These items are added to Inventory and held for the order waiting on them. This cannot be undone."
        footer={
          <>
            <Button onClick={() => setConfirmReceive(false)}>Not yet</Button>
            <Button
              variant="primary"
              loading={markReceived.isPending}
              onClick={() =>
                markReceived.mutate(p.id, {
                  onSuccess: () => {
                    setConfirmReceive(false);
                    toast.success(`${p.number} received. Stock and order updated.`);
                  },
                  onError: (e) => {
                    setConfirmReceive(false);
                    toast.error(errorMessage(e));
                  },
                })
              }
            >
              Yes, received
            </Button>
          </>
        }
      >
        <ul className="space-y-1 text-[13px] text-ink">
          {p.lines.map((l) => (
            <li key={l.id}>
              {l.description} × {l.quantity}
            </li>
          ))}
        </ul>
      </Modal>
    </>
  );
}

/**
 * Supplier, then one of its branches (if it has any). The GST number and
 * address shown are what the purchase order prints: the branch's when one is
 * picked, else the supplier's own, so they always follow the selection.
 */
function SupplierPicker({
  suppliers,
  value,
  onChange,
}: {
  suppliers: { id: number; name: string }[];
  value: { supplier: string; branch: string };
  onChange: (value: { supplier: string; branch: string }) => void;
}) {
  const party = useParty("suppliers", value.supplier ? Number(value.supplier) : null);
  const selected = party.data?.id === Number(value.supplier) ? party.data : undefined;
  const branches = (selected?.branches ?? []).filter(
    (b) => b.is_active || String(b.id) === value.branch,
  );
  const branch = branches.find((b) => String(b.id) === value.branch);
  const shipTo = !selected
    ? null
    : branch
      ? { gstin: branch.gstin, address: formatAddress(branch.address_line1, branch.city, branch.state, branch.pincode) }
      : {
          gstin: selected.gstin,
          address: formatAddress(
            [selected.address_line1, selected.address_line2].filter(Boolean).join(", "),
            selected.city,
            selected.state,
            selected.pincode,
          ),
        };

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <FormField label="Supplier">
        {(props) => (
          <Select
            {...props}
            value={value.supplier}
            // A branch belongs to one supplier: a new supplier starts at its head office.
            onChange={(e) => onChange({ supplier: e.target.value, branch: "" })}
          >
            <option value="">Choose a supplier…</option>
            {suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        )}
      </FormField>
      {selected ? (
        branches.length > 0 ? (
          <FormField label="Branch" hint="Optional. The branch's GST number and address print.">
            {(props) => (
              <Select
                {...props}
                value={value.branch}
                onChange={(e) => onChange({ supplier: value.supplier, branch: e.target.value })}
              >
                <option value="">Head office</option>
                {branches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name} · {b.code}
                  </option>
                ))}
              </Select>
            )}
          </FormField>
        ) : (
          <FormField label="Branch" hint="This supplier has no branches.">
            {(props) => <Input {...props} readOnly value="Head office" />}
          </FormField>
        )
      ) : (
        <div className="hidden md:block" />
      )}
      {shipTo ? (
        <>
          <FormField label="GST Number" hint="Filled in from the selection.">
            {(props) => <Input {...props} readOnly value={shipTo.gstin} placeholder="—" />}
          </FormField>
          <FormField label="Address" hint="Filled in from the selection.">
            {(props) => <Input {...props} readOnly value={shipTo.address} placeholder="—" />}
          </FormField>
        </>
      ) : null}
    </div>
  );
}
