import type { ReactNode, ThHTMLAttributes, TdHTMLAttributes } from "react";
import { cellCls, tableWrapCls, tbodyRowCls, theadRowCls } from "./styles";

/**
 * The wrapper owns the horizontal scroll, so a wide table never makes the page
 * itself scroll sideways at 360px.
 */
export function TableWrap({
  className = "",
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <div className={`${tableWrapCls} ${className}`}>{children}</div>;
}

export function Table({ children }: { children: ReactNode }) {
  return <table className="w-full border-collapse text-[13px]">{children}</table>;
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead>
      <tr className={theadRowCls}>{children}</tr>
    </thead>
  );
}

export interface THProps extends ThHTMLAttributes<HTMLTableCellElement> {
  /** Right-aligns the column; numeric cells also carry tabular-nums. */
  numeric?: boolean;
}

export function TH({ numeric, className = "", children, ...rest }: THProps) {
  return (
    <th
      scope="col"
      className={`${cellCls} whitespace-nowrap font-medium ${
        numeric ? "text-right" : ""
      } ${className}`}
      {...rest}
    >
      {children}
    </th>
  );
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody>{children}</tbody>;
}

export function TR({ children, onClick }: { children: ReactNode; onClick?: () => void }) {
  return (
    <tr className={`${tbodyRowCls} ${onClick ? "cursor-pointer" : ""}`} onClick={onClick}>
      {children}
    </tr>
  );
}

export interface TDProps extends TdHTMLAttributes<HTMLTableCellElement> {
  numeric?: boolean;
}

export function TD({ numeric, className = "", children, ...rest }: TDProps) {
  return (
    <td
      className={`${cellCls} ${numeric ? "text-right tabular-nums" : ""} ${className}`}
      {...rest}
    >
      {children}
    </td>
  );
}

/** Full-width row carrying an empty, error or loading state inside a table. */
export function TableMessageRow({
  colSpan,
  children,
}: {
  colSpan: number;
  children: ReactNode;
}) {
  return (
    <tr>
      <td colSpan={colSpan} className="p-0">
        {children}
      </td>
    </tr>
  );
}
