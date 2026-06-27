"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Download, Loader2 } from "lucide-react";
import { classNames } from "@/utils/format";

const ROWS_PER_PAGE_OPTIONS = [10, 25, 50, 100];

interface DataTableViewerProps {
  /** Raw data rows (objects). If provided, skips API fetch. */
  data?: Record<string, unknown>[];
  /** Column info { colName: { dtype, business_meaning } }. */
  columns?: Record<string, { dtype?: string; business_meaning?: string }>;
  /** CSV filename in temp_data/ — fetches from /api/v1/tables/{filename} */
  filename?: string;
  /** Display title */
  title?: string;
  /** Optional className */
  className?: string;
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/**
 * DataTableViewer — renders CSV data as an interactive table
 * with sort, pagination, and CSV export.
 *
 * Two modes:
 * 1. Pass `data` and `columns` directly (inline data)
 * 2. Pass `filename` → auto-fetches from GET /api/v1/tables/{filename}
 */
export function DataTableViewer({
  data: inlineData,
  columns: inlineColumns,
  filename,
  title,
  className = "",
}: DataTableViewerProps) {
  const [fetchedData, setFetchedData] = useState<Record<string, unknown>[] | null>(null);
  const [fetchedColumns, setFetchedColumns] = useState<Record<string, { dtype?: string; business_meaning?: string }> | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(ROWS_PER_PAGE_OPTIONS[0]);
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  // Fetch from API when filename is provided
  useEffect(() => {
    if (!filename) return;
    setLoading(true);
    setFetchError(null);
    fetch(`${API_BASE}/tables/${encodeURIComponent(filename)}`, {
      credentials: "include",
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
        return r.json();
      })
      .then((json) => {
        setFetchedData(json.data ?? []);
        setFetchedColumns(json.columns ?? {});
      })
      .catch((err) => {
        setFetchError(err.message);
        setFetchedData([]);
      })
      .finally(() => setLoading(false));
  }, [filename]);

  const data = inlineData ?? fetchedData ?? [];
  const columns = inlineColumns ?? fetchedColumns ?? {};

  const colNames = useMemo(
    () =>
      Object.keys(columns).length > 0
        ? Object.keys(columns)
        : data.length > 0
        ? Object.keys(data[0])
        : [],
    [columns, data]
  );

  // Sort
  const sortedData = useMemo(() => {
    if (!data || data.length === 0) return [];
    const rows = [...data];
    if (sortKey) {
      rows.sort((a, b) => {
        const va = a[sortKey];
        const vb = b[sortKey];
        if (va == null) return 1;
        if (vb == null) return -1;
        if (typeof va === "number" && typeof vb === "number") {
          return sortDir === "asc" ? va - vb : vb - va;
        }
        return sortDir === "asc"
          ? String(va).localeCompare(String(vb))
          : String(vb).localeCompare(String(va));
      });
    }
    return rows;
  }, [data, sortKey, sortDir]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(sortedData.length / rowsPerPage));
  const safePage = Math.min(currentPage, totalPages);
  const pageData = sortedData.slice(
    (safePage - 1) * rowsPerPage,
    safePage * rowsPerPage
  );

  const handleSort = useCallback(
    (key: string) => {
      if (sortKey === key) {
        setSortDir((p) => (p === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDir("asc");
      }
    },
    [sortKey]
  );

  // Export CSV
  const handleExportCSV = useCallback(() => {
    if (data.length === 0) return;
    const headers = colNames.join(",");
    const rows = data.map((row) =>
      colNames
        .map((col) => {
          const val = row[col];
          if (val == null) return "";
          const str = String(val);
          return str.includes(",") || str.includes('"') || str.includes("\n")
            ? `"${str.replace(/"/g, '""')}"`
            : str;
        })
        .join(",")
    );
    const csv = [headers, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${title || filename || "data"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [data, colNames, title, filename]);

  const displayTitle = title || filename || "Data Table";

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-8 text-white/40">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span className="text-sm">Loading table data...</span>
      </div>
    );
  }

  // Error state
  if (fetchError) {
    return (
      <div className="rounded-md border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-300">
        Failed to load table: {fetchError}
      </div>
    );
  }

  // Empty state
  if (!data || data.length === 0) {
    return (
      <div className="rounded-md border border-white/5 bg-bg/60 p-3 text-center text-sm text-white/40">
        No data to display.
      </div>
    );
  }

  return (
    <div className={classNames("my-3", className)}>
      {/* Header */}
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-white/50">
          <span className="font-medium text-white/70">{displayTitle}</span>
          <span>&middot; {sortedData.length} rows</span>
          {sortKey && (
            <span>
              &middot; Sorted by "{sortKey}"
            </span>
          )}
        </div>
        <button
          onClick={handleExportCSV}
          className="inline-flex items-center gap-1 rounded-md border border-white/10 px-2 py-1 text-xs text-white/60 hover:bg-white/5 hover:text-white/80 transition-colors"
          title="Export as CSV"
        >
          <Download className="h-3.5 w-3.5" />
          CSV
        </button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-white/5">
        <table className="min-w-full divide-y divide-white/5">
          <thead>
            <tr className="bg-white/[0.03]">
              {colNames.map((col) => (
                <th
                  key={col}
                  onClick={() => handleSort(col)}
                  className={classNames(
                    "px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer select-none transition-colors",
                    sortKey === col ? "text-accent" : "text-white/50 hover:text-white/70 hover:bg-white/5"
                  )}
                >
                  <div className="flex items-center gap-1">
                    <span>
                      {columns[col]?.business_meaning
                        ? `${col} (${columns[col].business_meaning})`
                        : col}
                    </span>
                    {sortKey === col && (
                      <span className="text-accent">
                        {sortDir === "asc" ? "\u25B2" : "\u25BC"}
                      </span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {pageData.map((row, ri) => (
              <tr
                key={ri}
                className="hover:bg-white/[0.02] transition-colors"
              >
                {colNames.map((col) => {
                  const val = row[col];
                  const display =
                    val == null ? (
                      <span className="text-white/20 italic">&mdash;</span>
                    ) : typeof val === "number" ? (
                      Number.isInteger(val)
                        ? val.toLocaleString()
                        : val.toFixed(4)
                    ) : (
                      String(val)
                    );
                  return (
                    <td
                      key={col}
                      className={classNames(
                        "px-3 py-2 text-sm whitespace-nowrap",
                        typeof val === "number"
                          ? "text-right font-mono text-white/80"
                          : "text-white/70"
                      )}
                    >
                      {display}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="mt-3 flex items-center justify-between text-sm">
        <div className="flex items-center gap-2">
          <span className="text-xs text-white/50">Show</span>
          <select
            value={rowsPerPage}
            onChange={(e) => {
              setRowsPerPage(Number(e.target.value));
              setCurrentPage(1);
            }}
            className="rounded-md border border-white/10 bg-bg-soft px-2 py-1 text-xs text-white/70 focus:border-accent focus:outline-none"
          >
            {ROWS_PER_PAGE_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          <span className="text-xs text-white/50">per page</span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-white/50">
            Page {safePage}/{totalPages}
          </span>
          <button
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={safePage <= 1}
            className="rounded-md border border-white/10 p-1 text-white/50 hover:bg-white/5 hover:text-white/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={safePage >= totalPages}
            className="rounded-md border border-white/10 p-1 text-white/50 hover:bg-white/5 hover:text-white/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}