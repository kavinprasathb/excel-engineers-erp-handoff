import { DataList } from "../../../components/ui/DataList";
import type { Column } from "../../../components/ui/DataList";
import { Pagination } from "../../../components/ui/Pagination";
import { Button } from "../../../components/ui/Button";
import { Badge } from "../../../components/ui/Badge";
import { ListStatus } from "../../../components/common/ListStatus";
import { ContactsCell } from "../../contacts/ContactsCell";
import { orDash } from "../../../lib/format";
import { useCustomers } from "../api";
import { CUSTOMER_FILTER_KEYS } from "../filterKeys";
import type { Customer } from "../../../api/types";
import type { ListParamsApi } from "../../../lib/useListParams";
import { useIsOwner } from "../../auth/api";

export function CustomersTable({
  params,
  onEdit,
  onDelete,
  onCreate,
}: {
  params: ListParamsApi;
  onEdit: (customer: Customer) => void;
  onDelete: (customer: Customer) => void;
  onCreate: () => void;
}) {
  const owner = useIsOwner();
  const activeRaw = params.get("is_active");
  const customers = useCustomers({
    q: params.get("q") || undefined,
    is_active: activeRaw === "" ? null : activeRaw === "true",
    page: params.page,
  });

  const columns: readonly Column<Customer>[] = [
    {
      key: "name",
      header: "Customer",
      primary: true,
      cell: (c) => (
        <div className="min-w-0">
          <p className="truncate font-medium text-ink">{c.name}</p>
          <p className="truncate text-[12px] text-ink-2">
            <span className="tabular-nums">{c.code}</span>
            {c.branches.some((b) => b.is_active)
              ? ` · ${c.branches.filter((b) => b.is_active).length} branch${c.branches.filter((b) => b.is_active).length === 1 ? "" : "es"}`
              : ""}
            {" · "}
            {orDash(c.contact_person)}
          </p>
          {c.missing_fields.length > 0 ? (
            <span title={`Missing: ${c.missing_fields.join(", ")}. Complete it on the next edit.`}>
              <Badge tone="amber">Needs details</Badge>
            </span>
          ) : null}
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      secondary: true,
      cell: (c) =>
        c.is_active ? <Badge tone="green">Active</Badge> : <Badge tone="gray">Inactive</Badge>,
    },
    {
      key: "phone",
      header: "Phone",
      cell: (c) => <ContactsCell values={c.phones ?? []} fallback={c.phone} />,
    },
    {
      key: "email",
      header: "Email",
      cell: (c) => <ContactsCell values={c.emails ?? []} fallback={c.email} />,
    },
    { key: "city", header: "Billing city", cell: (c) => orDash(c.billing_city) },
    { key: "gstin", header: "GSTIN", cell: (c) => orDash(c.gstin), hideOnMobile: true },
    {
      key: "actions",
      header: "Actions",
      cell: (c) => (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={() => onEdit(c)}>
            Edit
          </Button>
          {owner ? (<Button size="sm" onClick={() => onDelete(c)} disabled={!c.is_active}>
            Deactivate
          </Button>) : null}
        </div>
      ),
    },
  ];

  const data = customers.data;
  const filtered = params.hasFilters(CUSTOMER_FILTER_KEYS);

  return (
    <>
      <DataList
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(c) => c.id}
        message={
          <ListStatus
            isPending={customers.isPending}
            isError={customers.isError}
            error={customers.error}
            onRetry={() => customers.refetch()}
            errorTitle="Could not load customers"
            emptyIcon="customers"
            emptyTitle={filtered ? "No customers match this filter" : "No customers yet"}
            emptyDescription={
              filtered
                ? "Try a different search, or clear the filters."
                : "Add the companies you quote to so offers can be addressed to them."
            }
            emptyAction={
              filtered ? null : (
                <Button variant="primary" size="sm" onClick={onCreate}>
                  New customer
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
    </>
  );
}
