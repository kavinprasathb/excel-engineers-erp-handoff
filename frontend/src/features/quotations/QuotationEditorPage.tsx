import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { FormField } from "../../components/ui/FormField";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { Textarea } from "../../components/ui/Textarea";
import { Loading } from "../../components/ui/Spinner";
import { ErrorState } from "../../components/ui/ErrorState";
import { Modal } from "../../components/ui/Modal";
import { useToast } from "../../components/ui/toast-context";
import { errorMessage } from "../../lib/errors";
import { useCustomerOptions } from "../customers/api";
import { useParty } from "../contacts/branchApi";
import { formatAddress } from "../contacts/partyRules";
import { useSettings } from "../settings/api";
import {
  quotationPdfUrl,
  useCreateQuotation,
  useQuotation,
  useReviseQuotation,
  useSetQuotationStatus,
  useUpdateQuotation,
} from "./api";
import { LinesEditor } from "./components/LinesEditor";
import { TechSheetEditor } from "./components/TechSheetEditor";
import { OfferLayoutPicker } from "./components/OfferLayoutPicker";
import { suggestedLayout } from "./layouts";
import { DatasheetRows } from "./components/DatasheetRows";
import { TermsEditor } from "./components/TermsEditor";
import { useCreateOrderForQuotation, useOrderForQuotation } from "../orders/api";
import { StatusBadge } from "./status";
import { DECLINE_REASONS } from "../analytics/api";
import { STAGE_PATH, formatQuoteDate, stageLabel, stageOf } from "./format";
import { draftFrom, emptyDraft, nextKey, toCreate, toPatch, validate } from "./draft";
import type { Draft, DraftErrors } from "./draft";
import { QUOTATION_TYPES } from "../../api/types";
import type { PrintColumn, Quotation, QuotationStatus, QuotationType, VersionKind } from "../../api/types";

/**
 * One screen for creating and editing. The URL decides which: `/quotations/new`
 * has no id and starts from an empty draft; `/quotations/:id` loads the quote.
 *
 * A quote that is not the latest pending revision is shown read-only with
 * the same layout, so what the reader sees is what the letter said.
 */
export default function QuotationEditorPage() {
  const { id } = useParams();
  const quotationId = id === undefined ? null : Number(id);

  if (quotationId === null) return <Editor quotation={null} />;
  return <Loaded id={quotationId} />;
}

function Loaded({ id }: { id: number }) {
  const q = useQuotation(id);
  if (q.isPending) {
    return (
      <>
        <PageHeader title="Quotation" />
        <PageBody>
          <Loading />
        </PageBody>
      </>
    );
  }
  if (q.isError) {
    return (
      <>
        <PageHeader title="Quotation" />
        <PageBody>
          <ErrorState title="Could not load this quotation" error={q.error} onRetry={() => q.refetch()} />
        </PageBody>
      </>
    );
  }
  // Keyed on id + updated_at so a revise (new id) or a save (new stamp)
  // re-seeds the draft; typing does not, because the key does not change.
  return <Editor key={`${q.data.id}:${q.data.updated_at}`} quotation={q.data} />;
}

function Editor({ quotation }: { quotation: Quotation | null }) {
  const navigate = useNavigate();
  const toast = useToast();
  const customers = useCustomerOptions();
  const settings = useSettings();
  const create = useCreateQuotation();
  const update = useUpdateQuotation();
  const revise = useReviseQuotation();
  const setStatus = useSetQuotationStatus();
  const accepted = quotation?.status === "accepted";
  const order = useOrderForQuotation(quotation?.id ?? 0, accepted);
  const createOrder = useCreateOrderForQuotation();

  const [draft, setDraft] = useState<Draft>(() =>
    quotation ? draftFrom(quotation) : emptyDraft(),
  );
  const [errors, setErrors] = useState<DraftErrors>({});
  // New quotes show the defaults for the chosen type until the user touches
  // the terms; after that the type switch leaves them alone.
  const [termsTouched, setTermsTouched] = useState(quotation !== null);
  const [confirm, setConfirm] = useState<QuotationStatus | null>(null);
  const [reasonPick, setReasonPick] = useState("");
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState<string | null>(null);

  const readOnly = quotation !== null && (quotation.status !== "pending" || !quotation.is_latest);
  const busy = create.isPending || update.isPending || revise.isPending || setStatus.isPending;

  // Seed default terms once settings arrive (or when the type changes) for a
  // new quote whose terms have not been edited yet.
  const defaults = settings.data?.quotation_terms_defaults;
  const seedKey = `${draft.type}:${defaults ? "y" : "n"}`;
  const [seededFor, setSeededFor] = useState("");
  if (!termsTouched && defaults && seededFor !== seedKey) {
    setSeededFor(seedKey);
    setDraft((d) => ({
      ...d,
      terms: (defaults[d.type] ?? []).map((t) => ({
        key: nextKey(),
        label: t.label,
        text: t.text,
        included: true,
      })),
    }));
  }

  function field<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  // The chosen customer with its branches. The GST number and address shown
  // (and printed) are the branch's when one is picked, else the head office's,
  // so they always follow the current selection.
  const party = useParty("customers", draft.customer_id ? Number(draft.customer_id) : null);
  const selected = party.data?.id === Number(draft.customer_id) ? party.data : undefined;
  const branchOptions = (selected?.branches ?? []).filter(
    (b) => b.is_active || String(b.id) === draft.customer_branch_id,
  );
  const branch = branchOptions.find((b) => String(b.id) === draft.customer_branch_id);
  const billTo = !selected
    ? null
    : branch
      ? { gstin: branch.gstin, address: formatAddress(branch.address_line1, branch.city, branch.state, branch.pincode) }
      : {
          gstin: selected.gstin,
          address: formatAddress(
            [selected.billing_address_line1, selected.billing_address_line2].filter(Boolean).join(", "),
            selected.billing_city,
            selected.billing_state,
            selected.billing_pincode,
          ),
        };

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const found = validate(draft);
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    if (quotation === null) {
      create.mutate(toCreate(draft, !termsTouched && !defaults), {
        onSuccess: (q) => {
          toast.success(`${q.number} created.`);
          navigate(`/quotations/${q.id}`, { replace: true });
        },
        onError: (err) => setErrors({ form: errorMessage(err) }),
      });
    } else {
      update.mutate(
        { id: quotation.id, patch: toPatch(draft) },
        {
          onSuccess: (q) => {
            toast.success(`${q.number} saved.`);
            backToList(q);
          },
          onError: (err) => setErrors({ form: errorMessage(err) }),
        },
      );
    }
  }

  // Back to the list this quote belongs to: a negotiation lives on the
  // Negotiations page, a revised quotation on Revised Quotations, an
  // initial quote on Quotations.
  function backToList(q: Quotation) {
    navigate(STAGE_PATH[stageOf(q)]);
  }

  // Product, quantity or technical changes: a revised quotation (R).
  // Price only: a negotiation (N). Either way the new version opens to edit.
  function onRevise(kind: VersionKind) {
    if (!quotation) return;
    revise.mutate(
      { id: quotation.id, kind },
      {
        onSuccess: (q) => {
          toast.success(
            kind === "revision"
              ? `${stageLabel(q)} started as ${q.number}. Change the products or technical details.`
              : `${stageLabel(q)} started as ${q.number}. Change the prices.`,
          );
          navigate(`/quotations/${q.id}`);
        },
        onError: (err) => setErrors({ form: errorMessage(err) }),
      },
    );
  }

  function onDecide(status: QuotationStatus) {
    if (!quotation) return;
    // Stored as the picked label, or "Other: <words>", so analytics can count them.
    const fullReason = reasonPick === "Other" ? `Other: ${reason.trim()}` : reasonPick;
    if (status === "declined" && !reasonPick) {
      setReasonError("Choose the reason the customer declined.");
      return;
    }
    if (status === "declined" && reasonPick === "Other" && !reason.trim()) {
      setReasonError("Write the reason in a few words.");
      return;
    }
    setStatus.mutate(
      { id: quotation.id, status, reason: status === "declined" ? fullReason : "" },
      {
        onSuccess: (q) => {
          setConfirm(null);
          toast.success(
            status === "accepted" ? `${q.number} accepted. Its order is in Orders.` : `${q.number} marked ${status}.`,
          );
          backToList(q);
        },
        onError: (err) => {
          setConfirm(null);
          setErrors({ form: errorMessage(err) });
        },
      },
    );
  }

  const title = quotation ? quotation.number : "New quotation";
  const canDecide = quotation !== null && quotation.status === "pending" && quotation.is_latest;
  // Any version can start the next revision or negotiation, except once the
  // number is accepted — that is final. The server enforces it too.
  const canRevise = quotation !== null && quotation.status !== "accepted";
  // A negotiation changes prices only; products and technical details are
  // changed by a revised quotation.
  const priceOnly = quotation !== null && quotation.neg_no > 0;

  return (
    <>
      <PageHeader
        title={title}
        description={
          quotation
            ? `${stageLabel(quotation)} · ${formatQuoteDate(quotation.quote_date)} · ${quotation.customer.name}`
            : "Numbered when saved, from the type and the date."
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {quotation ? <StatusBadge status={quotation.status} /> : null}
            {quotation ? (
              <Button onClick={() => window.open(quotationPdfUrl(quotation.id), "_blank")}>
                Download PDF
              </Button>
            ) : null}
            {accepted && order.data ? (
              <Button variant="primary" onClick={() => navigate(`/orders/${order.data.id}`)}>
                View order
              </Button>
            ) : null}
            {accepted && order.isError && quotation ? (
              <Button
                variant="primary"
                loading={createOrder.isPending}
                onClick={() =>
                  createOrder.mutate(quotation.id, {
                    onSuccess: (o) => navigate(`/orders/${o.id}`),
                    onError: (err) => setErrors({ form: errorMessage(err) }),
                  })
                }
              >
                Create order
              </Button>
            ) : null}
            {quotation && (quotation.revision > 0 || !quotation.is_latest) ? (
              <Button onClick={() => navigate(`/negotiations/${quotation.id}`)}>
                Version history
              </Button>
            ) : null}
            {canRevise ? (
              <>
                <Button
                  onClick={() => onRevise("revision")}
                  disabled={busy}
                  title="The customer asked to change a product, quantity or technical detail."
                >
                  {quotation.is_latest ? "Revise quotation" : "Revise from this version"}
                </Button>
                <Button
                  onClick={() => onRevise("negotiation")}
                  disabled={busy}
                  title="The customer accepts the products and asks only for a better price."
                >
                  {quotation.is_latest ? "Negotiate price" : "Negotiate from this version"}
                </Button>
              </>
            ) : null}
            {canDecide ? (
              <>
                <Button variant="danger" onClick={() => setConfirm("declined")} disabled={busy}>
                  Decline
                </Button>
                <Button variant="dark" onClick={() => setConfirm("accepted")} disabled={busy}>
                  Accept
                </Button>
              </>
            ) : null}
          </div>
        }
      />
      <PageBody>
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          {quotation?.status === "declined" && quotation.decline_reason ? (
            <p className="rounded-md border border-red/30 bg-red-bg px-3 py-2 text-[13px] text-ink">
              <span className="font-medium">Declined:</span> {quotation.decline_reason}
            </p>
          ) : null}

          {readOnly && quotation ? (
            <p className="rounded-md border border-line bg-hoverfill px-3 py-2 text-[13px] text-ink-2">
              {quotation.status === "superseded"
                ? "An old version, kept as it went out. See Version history for the latest — or start the next revision or negotiation from this one."
                : quotation.status === "accepted"
                  ? `Accepted at ${stageLabel(quotation).toLowerCase()}. This is the final version.`
                  : "Declined. Revise it or negotiate to send a new version."}
            </p>
          ) : null}

          {priceOnly && !readOnly ? (
            <p className="rounded-md border border-line bg-hoverfill px-3 py-2 text-[13px] text-ink-2">
              A negotiation changes prices only. To change a product, quantity or technical detail,
              use <b>Revise quotation</b> instead.
            </p>
          ) : null}

          <Card>
            <CardHeader title="Addressed to" />
            <CardBody className="grid gap-4 md:grid-cols-2">
              <FormField label="Customer" required error={errors.customer_id}>
                {(p) => (
                  <Select
                    {...p}
                    value={draft.customer_id}
                    disabled={readOnly}
                    onChange={(e) =>
                      // A branch belongs to one customer: a new customer starts at its head office.
                      setDraft((d) => ({ ...d, customer_id: e.target.value, customer_branch_id: "" }))
                    }
                  >
                    <option value="">Choose a customer…</option>
                    {(customers.data ?? []).map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </Select>
                )}
              </FormField>
              <div className="grid gap-4 grid-cols-2">
                <FormField label="Type" required hint={quotation ? "Fixed once numbered." : undefined}>
                  {(p) => (
                    <Select
                      {...p}
                      value={draft.type}
                      disabled={readOnly || quotation !== null}
                      onChange={(e) => field("type", e.target.value as QuotationType)}
                    >
                      {QUOTATION_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>
                          {t.label} · {t.prefix}
                        </option>
                      ))}
                    </Select>
                  )}
                </FormField>
                <FormField label="Date" required error={errors.quote_date}>
                  {(p) => (
                    <Input
                      {...p}
                      type="date"
                      value={draft.quote_date}
                      readOnly={readOnly}
                      onChange={(e) => field("quote_date", e.target.value)}
                    />
                  )}
                </FormField>
              </div>
              {selected ? (
                <div className="grid gap-4 md:col-span-2 md:grid-cols-[minmax(12rem,1fr)_12rem_2fr]">
                  {branchOptions.length > 0 ? (
                    <FormField label="Branch" hint="Optional. The branch's GST number and address print.">
                      {(p) => (
                        <Select
                          {...p}
                          value={draft.customer_branch_id}
                          disabled={readOnly}
                          onChange={(e) => field("customer_branch_id", e.target.value)}
                        >
                          <option value="">Head office</option>
                          {branchOptions.map((b) => (
                            <option key={b.id} value={b.id}>
                              {b.name} · {b.code}
                            </option>
                          ))}
                        </Select>
                      )}
                    </FormField>
                  ) : (
                    <FormField label="Branch" hint="This customer has no branches.">
                      {(p) => <Input {...p} readOnly value="Head office" />}
                    </FormField>
                  )}
                  <FormField label="GST Number" hint="Filled in from the selection.">
                    {(p) => <Input {...p} readOnly value={billTo?.gstin ?? ""} placeholder="—" />}
                  </FormField>
                  <FormField label="Address" hint="Filled in from the selection.">
                    {(p) => <Input {...p} readOnly value={billTo?.address ?? ""} placeholder="—" />}
                  </FormField>
                </div>
              ) : null}
              <FormField label="Subject" hint='Printed as "Sub.: …" and echoed in the opening line.'>
                {(p) => (
                  <Input
                    {...p}
                    placeholder="Offer for RNS Coupling"
                    value={draft.subject}
                    readOnly={readOnly}
                    onChange={(e) => field("subject", e.target.value)}
                  />
                )}
              </FormField>
              <FormField label="Reference" hint='Printed as "Ref.: …". Leave blank to omit.'>
                {(p) => (
                  <Input
                    {...p}
                    placeholder="Telecon"
                    value={draft.reference}
                    readOnly={readOnly}
                    onChange={(e) => field("reference", e.target.value)}
                  />
                )}
              </FormField>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Offer layout"
              description="How the letter is laid out. The items stay the same; change it at any time before a negotiation."
            />
            <CardBody>
              <OfferLayoutPicker
                value={draft.format}
                suggested={suggestedLayout(draft.type, draft.lines)}
                locked={readOnly || priceOnly}
                onChange={(format) => field("format", format)}
              />
            </CardBody>
          </Card>

          {draft.format === "technical" ? (
            <Card>
              <CardHeader
                title="Technical offer"
                description="One column per pump, one row per technical parameter. Whole rupees, excluding GST."
              />
              <CardBody>
                <TechSheetEditor
                  rows={draft.tech_rows}
                  lines={draft.lines}
                  scope={draft.scope}
                  onRows={(rows) => field("tech_rows", rows)}
                  onLines={(lines) => field("lines", lines)}
                  onScope={(scope) => field("scope", scope)}
                  priceLabel={draft.price_label}
                  onPriceLabel={(label) => field("price_label", label)}
                  errors={errors.line ?? {}}
                  listError={errors.lines}
                  readOnly={readOnly}
                  priceOnly={priceOnly}
                />
              </CardBody>
            </Card>
          ) : (
          <Card>
            <CardHeader
              title={draft.format === "spares" ? "Spares & service" : "Pumps"}
              description={
                draft.format === "spares"
                  ? "Group parts under each pump model; each group prints with its subtotal. Whole rupees, excluding GST."
                  : "Each pump prints with its datasheet, scope of supply and price. Whole rupees, excluding GST."
              }
            />
            <CardBody className="space-y-3">
              {draft.format === "spares" ? (
                <div className="flex flex-wrap items-center gap-2 rounded-lg border border-line bg-hoverfill/60 p-3">
                  <span className="text-[13px] font-semibold text-ink">Columns to print</span>
                  {(
                    [
                      ["part_no", "Part No"],
                      ["moc", "MOC"],
                      ["unit", "Unit"],
                      ["delivery", "Delivery"],
                    ] as [PrintColumn, string][]
                  ).map(([key, label]) => {
                    const on = draft.print_columns.includes(key);
                    return (
                      <button
                        key={key}
                        type="button"
                        aria-pressed={on}
                        disabled={readOnly}
                        onClick={() =>
                          field(
                            "print_columns",
                            on ? draft.print_columns.filter((c) => c !== key) : [...draft.print_columns, key],
                          )
                        }
                        className={`rounded-full border px-3 py-1 text-[12.5px] font-medium transition ${
                          on ? "border-brand bg-brand text-white" : "border-line bg-card text-ink-2 hover:border-brand/50"
                        }`}
                      >
                        {label}
                      </button>
                    );
                  })}
                  <span className="text-[12px] text-ink-2">Sl, Description, Qty, Rate and Total always print.</span>
                </div>
              ) : (
                <DatasheetRows
                  rows={draft.tech_rows}
                  onChange={(rows) => field("tech_rows", rows)}
                  readOnly={readOnly || priceOnly}
                />
              )}
              <LinesEditor
                layout={draft.format === "spares" ? "spares" : "pump"}
                datasheetRows={draft.tech_rows}
                printColumns={draft.print_columns}
                customerId={draft.customer_id ? Number(draft.customer_id) : null}
                lines={draft.lines}
                onChange={(lines) => field("lines", lines)}
                errors={errors.line ?? {}}
                listError={errors.lines}
                readOnly={readOnly}
                priceOnly={priceOnly}
              />
            </CardBody>
          </Card>
          )}

          <Card>
            <CardHeader
              title="Commercial terms"
              description="Ticked terms print on the letter. Edit any line for this quotation only."
            />
            <CardBody>
              <TermsEditor
                terms={draft.terms}
                readOnly={readOnly}
                onChange={(terms) => {
                  setTermsTouched(true);
                  field("terms", terms);
                }}
              />
            </CardBody>
          </Card>


          <Card>
            <CardHeader title="Internal notes" description="Never printed." />
            <CardBody>
              <Textarea
                aria-label="Internal notes"
                value={draft.notes}
                readOnly={readOnly}
                onChange={(e) => field("notes", e.target.value)}
              />
            </CardBody>
          </Card>

          {errors.form ? (
            <p className="text-[13px] text-red" role="alert">
              {errors.form}
            </p>
          ) : null}

          {readOnly ? null : (
            <div className="flex flex-wrap justify-end gap-2">
              <Button onClick={() => navigate("/quotations")}>Cancel</Button>
              <Button type="submit" variant="primary" loading={create.isPending || update.isPending}>
                {quotation ? "Save changes" : "Create quotation"}
              </Button>
            </div>
          )}
        </form>
      </PageBody>

      <Modal
        open={confirm !== null}
        onClose={() => {
          setConfirm(null);
          setReasonError(null);
        }}
        title={confirm === "accepted" ? "Mark as accepted?" : "Mark as declined?"}
        description={
          confirm === "accepted"
            ? "This becomes the final version of the number; no further negotiation."
            : "The quotation is locked afterwards. A new negotiation can still be started from it."
        }
        footer={
          <>
            <Button
              onClick={() => {
                setConfirm(null);
                setReasonError(null);
              }}
            >
              Keep pending
            </Button>
            <Button
              variant={confirm === "accepted" ? "dark" : "danger"}
              loading={setStatus.isPending}
              onClick={() => confirm && onDecide(confirm)}
            >
              {confirm === "accepted" ? "Accept" : "Decline"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <p className="text-[13px] text-ink-2">
            {quotation?.number} for {quotation?.customer.name}.
          </p>
          {confirm === "declined" ? (
            <FormField
              label="Reason"
              required
              error={reasonError ?? undefined}
              hint="Why the customer said no. Kept on the quotation, never printed; counted in Analytics."
            >
              {(p) => (
                <Select
                  {...p}
                  autoFocus
                  value={reasonPick}
                  onChange={(e) => {
                    setReasonPick(e.target.value);
                    if (reasonError) setReasonError(null);
                  }}
                >
                  <option value="">Choose a reason…</option>
                  {DECLINE_REASONS.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                  <option value="Other">Other…</option>
                </Select>
              )}
            </FormField>
          ) : null}
          {confirm === "declined" && reasonPick === "Other" ? (
            <FormField label="Other reason" required>
              {(p) => (
                <Textarea
                  {...p}
                  value={reason}
                  onChange={(e) => {
                    setReason(e.target.value);
                    if (reasonError) setReasonError(null);
                  }}
                />
              )}
            </FormField>
          ) : null}
        </div>
      </Modal>
    </>
  );
}
