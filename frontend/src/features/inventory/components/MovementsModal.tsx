import { useState } from "react";
import { Modal } from "../../../components/ui/Modal";
import { Button } from "../../../components/ui/Button";
import { DataList } from "../../../components/ui/DataList";
import type { Column } from "../../../components/ui/DataList";
import { Pagination } from "../../../components/ui/Pagination";
import { Badge } from "../../../components/ui/Badge";
import type { BadgeTone } from "../../../components/ui/Badge";
import { ListStatus } from "../../../components/common/ListStatus";
import { EMPTY, formatDateTime, formatNumber, orDash } from "../../../lib/format";
import { useMovements } from "../api";
import type { InventoryRow, Movement, MovementType } from "../../../api/types";

const TYPE_LABEL: Record<MovementType, string> = {
  receive: "Received",
  adjust: "Adjusted",
  reserve: "Reserved",
  release: "Released",
  deliver: "Delivered",
  import: "Imported",
};

const TYPE_TONE: Record<MovementType, BadgeTone> = {
  receive: "green",
  adjust: "brand",
  reserve: "amber",
  release: "gray",
  deliver: "red",
  import: "brand",
};

/** A signed count, with the sign kept — `0` and `+0` are different news. */
function Delta({ value }: { value: number }) {
  if (value === 0) return <span className="text-ink-2">{EMPTY}</span>;
  return (
    <span className={`tabular-nums ${value > 0 ? "text-green" : "text-red"}`}>
      {value > 0 ? "+" : "−"}
      {formatNumber(Math.abs(value))}
    </span>
  );
}

const columns: readonly Column<Movement>[] = [
  {
    key: "when",
    header: "When",
    primary: true,
    cell: (m) => formatDateTime(m.created_at),
  },
  {
    key: "type",
    header: "Type",
    secondary: true,
    cell: (m) => <Badge tone={TYPE_TONE[m.movement_type]}>{TYPE_LABEL[m.movement_type]}</Badge>,
  },
  { key: "onHandDelta", header: "On hand", numeric: true, cell: (m) => <Delta value={m.on_hand_delta} /> },
  {
    key: "reservedDelta",
    header: "Reserved",
    numeric: true,
    cell: (m) => <Delta value={m.reserved_delta} />,
  },
  {
    key: "after",
    header: "After",
    numeric: true,
    cell: (m) => (
      <span className="tabular-nums">
        {formatNumber(m.quantity_on_hand_after)} / {formatNumber(m.quantity_reserved_after)}
      </span>
    ),
  },
  { key: "note", header: "Note", cell: (m) => orDash(m.note) },
  { key: "by", header: "By", cell: (m) => orDash(m.created_by?.full_name) },
];

export function MovementsModal({
  row,
  onClose,
}: {
  row: InventoryRow | null;
  onClose: () => void;
}) {
  // Paging resets with the modal because the modal is unmounted on close.
  const [page, setPage] = useState(1);
  const movements = useMovements(row?.product_id ?? null, page);

  if (!row) return null;

  const data = movements.data;

  return (
    <Modal
      open
      onClose={onClose}
      title="Movement history"
      description={`${row.name} · ${row.sku}`}
      footer={<Button onClick={onClose}>Close</Button>}
    >
      <DataList
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(m) => m.id}
        message={
          <ListStatus
            isPending={movements.isPending}
            isError={movements.isError}
            error={movements.error}
            onRetry={() => movements.refetch()}
            errorTitle="Could not load the movement history"
            emptyTitle="No stock movements yet"
            emptyDescription="Receiving, adjusting or reserving this product will show up here."
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
            onPageChange={setPage}
          />
        </div>
      ) : null}
    </Modal>
  );
}
