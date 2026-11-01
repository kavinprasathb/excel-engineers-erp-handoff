import { useState } from "react";
import { DataList } from "../../../components/ui/DataList";
import { Modal } from "../../../components/ui/Modal";
import { useToast } from "../../../components/ui/toast-context";
import { errorMessage } from "../../../lib/errors";
import type { Column } from "../../../components/ui/DataList";
import { Pagination } from "../../../components/ui/Pagination";
import { Button } from "../../../components/ui/Button";
import { ListStatus } from "../../../components/common/ListStatus";
import { orDash } from "../../../lib/format";
import { useDeleteQuotation, useQuotations } from "../api";
import { QUOTATION_FILTER_KEYS } from "../filterKeys";
import { StatusBadge } from "../status";
import { formatQuoteDate, formatRupees, stageLabel, typeLabel } from "../format";
import { QUOTATION_STATUSES, QUOTATION_TYPES } from "../../../api/types";
import type { QuotationSummary } from "../../../api/types";
import type { ListParamsApi } from "../../../lib/useListParams";
import { useIsOwner } from "../../auth/api";

export function QuotationsTable({
  params,
  onOpen,
  onCreate,
  stage,
}: {
  params: ListParamsApi;
  onOpen: (q: QuotationSummary) => void;
  onCreate?: () => void;
  /**
   * Only numbers whose latest version is a revised quotation (the Revised
   * Quotations page) or a negotiation (the Negotiations page). Unset: all.
   */
  stage?: "revised" | "negotiation";
}) {
  const negotiated = stage === "negotiation";
  const revised = stage === "revised";
  const owner = useIsOwner();
  // Narrow rather than cast: a stale ?status=junk in a pasted URL must become
  // "no filter", not a 422 from the server.
  const type = QUOTATION_TYPES.find((t) => t.value === params.get("type"))?.value;
  const status = QUOTATION_STATUSES.find((s) => s === params.get("status"));
  const quotations = useQuotations({
    q: params.get("q") || undefined,
    type,
    status,
    stage,
    page: params.page,
  });

  const toast = useToast();
  const remove = useDeleteQuotation();
  const [toDelete, setToDelete] = useState<QuotationSummary | null>(null);

  const columns: readonly Column<QuotationSummary>[] = [
    {
      key: "number",
      header: "Number",
      primary: true,
      cell: (q) => (
        <div className="min-w-0">
          <p className="truncate font-medium text-ink">{q.number}</p>
          <p className="truncate text-[12px] text-ink-2">
            {typeLabel(q.type)}
            {q.revision > 0 ? ` · ${stageLabel(q)}` : ""}
          </p>
        </div>
      ),
    },
    { key: "customer", header: "Customer", cell: (q) => q.customer.name },
    { key: "subject", header: "Subject", cell: (q) => orDash(q.subject), hideOnMobile: true },
    { key: "date", header: "Date", cell: (q) => formatQuoteDate(q.quote_date) },
    { key: "total", header: "Total (ex-GST)", numeric: true, cell: (q) => formatRupees(q.total_paise) },
    {
      key: "actions",
      header: "",
      cell: (q) => (
        // Buttons inside a clickable row: stop the click reaching the row.
        <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
          <Button size="sm" onClick={() => onOpen(q)}>
            {q.status === "pending" ? "Edit" : "View"}
          </Button>
          {owner ? (
          <Button size="sm" variant="danger" disabled={q.status === "accepted"} title={q.status === "accepted" ? "Accepted quotes have an order and cannot be deleted" : undefined} onClick={() => setToDelete(q)}>
            Delete
          </Button>
          ) : null}
        </div>
      ),
    },
    // Last, where the eye lands after reading the row. The row itself opens it.
    { key: "status", header: "Status", secondary: true, cell: (q) => <StatusBadge status={q.status} /> },
  ];

  const data = quotations.data;
  const filtered = params.hasFilters(QUOTATION_FILTER_KEYS);

  return (
    <>
      <DataList
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(q) => q.id}
        onRowClick={onOpen}
        message={
          <ListStatus
            isPending={quotations.isPending}
            isError={quotations.isError}
            error={quotations.error}
            onRetry={() => quotations.refetch()}
            errorTitle="Could not load quotations"
            emptyIcon="quotations"
            emptyTitle={
              filtered
                ? "Nothing matches this filter"
                : negotiated
                  ? "No negotiations yet"
                  : revised
                    ? "No revised quotations yet"
                    : "No quotations yet"
            }
            emptyDescription={
              filtered
                ? "Try a different search, or clear the filters."
                : negotiated
                  ? "When a customer asks only for a better price, open the quote and press Negotiate price."
                  : revised
                    ? "When a customer asks to change a product, quantity or technical detail, open the quote and press Revise quotation."
                    : "Write the first offer and download it as the letter."
            }
            emptyAction={
              filtered || !onCreate ? null : (
                <Button variant="primary" size="sm" onClick={onCreate}>
                  New quotation
                </Button>
              )
            }
          />
        }
      />

      {data && data.total > 0 ? (
        <div className="mt-3">
          <Pagination
            page={data.page}
            pages={data.pages}
            total={data.total}
            pageSize={data.page_size}
            onPageChange={params.setPage}
          />
        </div>
      ) : null}

      <Modal
        open={toDelete !== null}
        onClose={() => setToDelete(null)}
        title={stage ? `Delete ${toDelete?.number ?? ""}?` : `Delete quotation ${toDelete?.number ?? ""}?`}
        description={
          stage
            ? `Only this ${negotiated ? "negotiation" : "revised quotation"} is deleted; earlier versions are kept, and the one before it becomes pending again. This cannot be undone.`
            : toDelete && toDelete.revision > 0
              ? "The quotation and all its revisions and negotiations are deleted. This cannot be undone."
              : "The quotation is deleted. This cannot be undone."
        }
        footer={
          <>
            <Button onClick={() => setToDelete(null)}>Keep it</Button>
            <Button
              variant="danger"
              loading={remove.isPending}
              onClick={() => {
                if (!toDelete) return;
                const number = toDelete.number;
                remove.mutate(
                  { id: toDelete.id, whole: !stage },
                  {
                    onSuccess: () => {
                      setToDelete(null);
                      toast.success(`${number} deleted.`);
                    },
                    onError: (e) => {
                      setToDelete(null);
                      toast.error(errorMessage(e));
                    },
                  },
                );
              }}
            >
              Delete
            </Button>
          </>
        }
      >
        <p className="text-[13px] text-ink">
          {toDelete?.customer.name} · {toDelete ? formatRupees(toDelete.total_paise) : ""}
        </p>
      </Modal>
    </>
  );
}
