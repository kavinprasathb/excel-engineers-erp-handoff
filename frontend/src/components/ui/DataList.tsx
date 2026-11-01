import type { ReactNode } from "react";
import { Table, TBody, TD, TH, THead, TR, TableWrap } from "./Table";
import { cardCls } from "./styles";

/**
 * One column definition drives two renderings: a real table from `md` up, and
 * a stack of label/value cards below it.
 *
 * Sideways scrolling is what makes an ERP list unusable on a phone — you
 * cannot see the SKU and the quantity at the same time. Reflowing costs more
 * markup than an overflow-x wrapper, but it is the only version that works at
 * 360px, so it is the default for the main lists. Use TableWrap directly for
 * secondary tables where scrolling is acceptable.
 */
export interface Column<Row> {
  key: string;
  header: string;
  cell: (row: Row) => ReactNode;
  numeric?: boolean;
  /** Becomes the mobile card's title instead of getting a label. */
  primary?: boolean;
  /** Sits beside the title, unlabelled — a SKU or a status chip. */
  secondary?: boolean;
  /** Dropped from the mobile card entirely, to keep it a readable length. */
  hideOnMobile?: boolean;
}

export interface DataListProps<Row> {
  columns: readonly Column<Row>[];
  rows: readonly Row[];
  rowKey: (row: Row) => string | number;
  onRowClick?: (row: Row) => void;
  /** Rendered in place of the rows when there are none. */
  message?: ReactNode;
}

export function DataList<Row>({
  columns,
  rows,
  rowKey,
  onRowClick,
  message,
}: DataListProps<Row>) {
  const primary = columns.find((c) => c.primary) ?? columns[0];
  const secondary = columns.filter((c) => c.secondary);
  const detail = columns.filter((c) => c !== primary && !c.secondary && !c.hideOnMobile);

  if (rows.length === 0 && message) {
    return <div className={cardCls}>{message}</div>;
  }

  return (
    <>
      <div className="hidden md:block">
        <TableWrap>
          <Table>
            <THead>
              {columns.map((c) => (
                <TH key={c.key} numeric={c.numeric}>
                  {c.header}
                </TH>
              ))}
            </THead>
            <TBody>
              {rows.map((row) => (
                <TR key={rowKey(row)} onClick={onRowClick ? () => onRowClick(row) : undefined}>
                  {columns.map((c) => (
                    <TD key={c.key} numeric={c.numeric}>
                      {c.cell(row)}
                    </TD>
                  ))}
                </TR>
              ))}
            </TBody>
          </Table>
        </TableWrap>
      </div>

      <ul className="space-y-2 md:hidden">
        {rows.map((row) => (
          <li key={rowKey(row)}>
            <div
              className={`${cardCls} p-3 ${onRowClick ? "cursor-pointer" : ""}`}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1 text-[13px] font-medium text-ink">
                  {primary.cell(row)}
                </div>
                {secondary.map((c) => (
                  <span key={c.key} className="shrink-0 text-[12px] text-ink-2">
                    {c.cell(row)}
                  </span>
                ))}
              </div>
              <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1.5">
                {detail.map((c) => (
                  <div key={c.key} className="min-w-0">
                    <dt className="text-[10px] font-medium uppercase tracking-wide text-ink-2">
                      {c.header}
                    </dt>
                    <dd
                      className={`truncate text-[13px] text-ink ${
                        c.numeric ? "tabular-nums" : ""
                      }`}
                    >
                      {c.cell(row)}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}
