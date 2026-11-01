import { DataList } from "../../../components/ui/DataList";
import type { Column } from "../../../components/ui/DataList";
import { Pagination } from "../../../components/ui/Pagination";
import { Button } from "../../../components/ui/Button";
import { Badge } from "../../../components/ui/Badge";
import { ListStatus } from "../../../components/common/ListStatus";
import { ContactsCell } from "../../contacts/ContactsCell";
import { formatNumber, orDash } from "../../../lib/format";
import { useSuppliers } from "../api";
import { SUPPLIER_FILTER_KEYS } from "../filterKeys";
import type { Supplier } from "../../../api/types";
import type { ListParamsApi } from "../../../lib/useListParams";
import { useIsOwner } from "../../auth/api";

export function SuppliersTable({
  params,
  onEdit,
  onDelete,
  onCreate,
}: {
  params: ListParamsApi;
  onEdit: (supplier: Supplier) => void;
  onDelete: (supplier: Supplier) => void;
  onCreate: () => void;
}) {
  const owner = useIsOwner();
  const activeRaw = params.get("is_active");
  const suppliers = useSuppliers({
    q: params.get("q") || undefined,
    is_active: activeRaw === "" ? null : activeRaw === "true",
    page: params.page,
  });

  const columns: readonly Column<Supplier>[] = [
    {
      key: "name",
      header: "Supplier",
      primary: true,
      cell: (s) => (
        <div className="min-w-0">
          <p className="truncate font-medium text-ink">{s.name}</p>
          <p className="truncate text-[12px] text-ink-2">
            <span className="tabular-nums">{s.code}</span>
            {s.branches.some((b) => b.is_active)
              ? ` · ${s.branches.filter((b) => b.is_active).length} branch${s.branches.filter((b) => b.is_active).length === 1 ? "" : "es"}`
              : ""}
            {" · "}
            {orDash(s.contact_person)}
          </p>
          {s.missing_fields.length > 0 ? (
            <span title={`Missing: ${s.missing_fields.join(", ")}. Complete it on the next edit.`}>
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
      cell: (s) =>
        s.is_active ? <Badge tone="green">Active</Badge> : <Badge tone="gray">Inactive</Badge>,
    },
    {
      key: "phone",
      header: "Phone",
      cell: (s) => <ContactsCell values={s.phones ?? []} fallback={s.phone} />,
    },
    {
      key: "email",
      header: "Email",
      cell: (s) => <ContactsCell values={s.emails ?? []} fallback={s.email} />,
    },
    { key: "city", header: "City", cell: (s) => orDash(s.city) },
    { key: "gstin", header: "GSTIN", cell: (s) => orDash(s.gstin), hideOnMobile: true },
    {
      key: "products",
      header: "Products",
      numeric: true,
      cell: (s) => formatNumber(s.product_count),
    },
    {
      key: "actions",
      header: "Actions",
      cell: (s) => (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={() => onEdit(s)}>
            Edit
          </Button>
          {owner ? (<Button size="sm" onClick={() => onDelete(s)} disabled={!s.is_active}>
            Deactivate
          </Button>) : null}
        </div>
      ),
    },
  ];

  const data = suppliers.data;
  const filtered = params.hasFilters(SUPPLIER_FILTER_KEYS);

  return (
    <>
      <DataList
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(s) => s.id}
        message={
          <ListStatus
            isPending={suppliers.isPending}
            isError={suppliers.isError}
            error={suppliers.error}
            onRetry={() => suppliers.refetch()}
            errorTitle="Could not load suppliers"
            emptyIcon="suppliers"
            emptyTitle={filtered ? "No suppliers match this filter" : "No suppliers yet"}
            emptyDescription={
              filtered
                ? "Try a different search, or clear the filters."
                : "Add the companies you buy from so products can be tagged to them."
            }
            emptyAction={
              filtered ? null : (
                <Button variant="primary" size="sm" onClick={onCreate}>
                  New supplier
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
