"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

import { classNames } from "@/utils/format";

export interface Column<T> {
  key: keyof T | string;
  header: string;
  accessor?: (row: T) => React.ReactNode;
  sortable?: boolean;
  sortKey?: string; // overrides `key` when emitting sortBy param
  className?: string;
}

interface DataTableProps<T> {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string | number;
  onRowClick?: (row: T) => void;
  sortBy?: string;
  sortDir?: "asc" | "desc";
  onSortChange?: (sortBy: string, sortDir: "asc" | "desc") => void;
  emptyText?: string;
  isLoading?: boolean;
}

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  onRowClick,
  sortBy,
  sortDir,
  onSortChange,
  emptyText = "No data.",
  isLoading = false,
}: DataTableProps<T>) {
  return (
    <div className="overflow-hidden border border-line">
      <div className="relative overflow-x-auto">
        {isLoading && (
          <div className="pointer-events-none absolute inset-x-0 top-0 h-0.5 animate-pulse bg-accent/60" />
        )}
        <table className="w-full text-sm">
          <thead className="bg-bg-soft text-left text-xs uppercase tracking-wide text-muted">
            <tr>
              {columns.map((c) => {
                const k = String(c.key);
                const sortable = c.sortable && onSortChange;
                const active = sortable && sortBy === (c.sortKey ?? k);
                return (
                  <th
                    key={k}
                    className={classNames(
                      "whitespace-nowrap px-3 py-2 font-medium",
                      c.className
                    )}
                  >
                    {sortable ? (
                      <button
                        type="button"
                        onClick={() => {
                          const nextDir =
                            active && sortDir === "asc" ? "desc" : "asc";
                          onSortChange(c.sortKey ?? k, nextDir);
                        }}
                        className="inline-flex items-center gap-1 hover:text-fg"
                      >
                        {c.header}
                        {active ? (
                          sortDir === "asc" ? (
                            <ArrowUp className="h-3 w-3" />
                          ) : (
                            <ArrowDown className="h-3 w-3" />
                          )
                        ) : (
                          <ArrowUpDown className="h-3 w-3 opacity-50" />
                        )}
                      </button>
                    ) : (
                      c.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-3 py-8 text-center text-muted">
                  {isLoading ? "Loading..." : emptyText}
                </td>
              </tr>
            )}
            {rows.map((r) => (
              <tr
                key={rowKey(r)}
                onClick={onRowClick ? () => onRowClick(r) : undefined}
                className={classNames(
                  "border-t border-line",
                  onRowClick && "cursor-pointer hover:bg-bg-soft"
                )}
              >
                {columns.map((c) => {
                  const k = String(c.key);
                  const value =
                    typeof c.accessor === "function"
                      ? c.accessor(r)
                      : (r as Record<string, unknown>)[k] as React.ReactNode;
                  return (
                    <td key={k} className={classNames("px-3 py-2 align-top", c.className)}>
                      {value as React.ReactNode}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
