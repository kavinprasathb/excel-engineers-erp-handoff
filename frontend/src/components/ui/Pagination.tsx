import { Button } from "./Button";
import { Icon } from "./Icon";
import { formatNumber } from "../../lib/format";

export interface PaginationProps {
  page: number;
  pages: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

/**
 * Prev / next plus an honest count. No numbered page buttons: at 360px they
 * wrap into a second row, and the range readout is the part anyone actually
 * uses to know where they are in 1,340 rows.
 */
export function Pagination({ page, pages, total, pageSize, onPageChange }: PaginationProps) {
  if (total === 0) return null;

  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);

  return (
    <nav
      aria-label="Pagination"
      className="flex flex-col gap-3 border-t border-line pt-3 sm:flex-row sm:items-center sm:justify-between"
    >
      <p className="text-[13px] text-ink-2">
        Showing <span className="tabular-nums text-ink">{formatNumber(first)}</span>–
        <span className="tabular-nums text-ink">{formatNumber(last)}</span> of{" "}
        <span className="tabular-nums text-ink">{formatNumber(total)}</span>
      </p>

      <div className="flex items-center gap-2">
        <Button
          size="sm"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          aria-label="Previous page"
          className="flex-1 sm:flex-none"
        >
          <Icon name="chevronLeft" size={15} />
          Previous
        </Button>
        <span className="shrink-0 text-[13px] tabular-nums text-ink-2">
          {formatNumber(page)} / {formatNumber(Math.max(pages, 1))}
        </span>
        <Button
          size="sm"
          disabled={page >= pages}
          onClick={() => onPageChange(page + 1)}
          aria-label="Next page"
          className="flex-1 sm:flex-none"
        >
          Next
          <Icon name="chevronRight" size={15} />
        </Button>
      </div>
    </nav>
  );
}
