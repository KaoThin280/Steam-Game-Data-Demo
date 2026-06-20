"use client";

import Link from "next/link";
import { useMemo } from "react";

import { DataTable, type Column } from "@/components/common/DataTable";
import { Pagination } from "@/components/common/Pagination";
import { FilterBar, type FilterField } from "@/components/common/FilterBar";
import { useFilters } from "@/hooks/useFilters";
import { useGames } from "@/hooks/useGames";
import type { Game, GameFilter } from "@/lib/types";
import { formatDate } from "@/utils/format";

const FILTER_FIELDS: FilterField[] = [
  { key: "search", label: "Search", type: "search", placeholder: "Name, developer, publisher..." },
  { key: "genre", label: "Genre", type: "text", placeholder: "e.g. Action" },
  { key: "category", label: "Category", type: "text", placeholder: "e.g. Multi-player" },
  { key: "developer", label: "Developer", type: "text" },
  { key: "publisher", label: "Publisher", type: "text" },
  { key: "is_free", label: "Free?", type: "boolean" },
  { key: "year", label: "Release year", type: "number" },
  {
    key: "sort_by",
    label: "Sort by",
    type: "select",
    options: [
      { value: "release_date", label: "Release date" },
      { value: "name", label: "Name" },
      { value: "required_age", label: "Required age" },
    ],
  },
  {
    key: "sort_order",
    label: "Order",
    type: "select",
    options: [
      { value: "asc", label: "Ascending" },
      { value: "desc", label: "Descending" },
    ],
  },
];

interface GameListTableProps {
  /** Hide internal filter bar (parent already provides one). */
  embedded?: boolean;
}

export function GameListTable({ embedded = false }: GameListTableProps) {
  const { filters, setFilter, reset } = useFilters<GameFilter>({
    page: 1,
    page_size: 20,
    sort_by: "release_date",
    sort_order: "desc",
  });

  const { data, isLoading } = useGames(filters);
  const rows = data?.items ?? [];
  const total = data?.total ?? 0;

  const columns: Column<Game>[] = useMemo(
    () => [
      {
        key: "name",
        header: "Name",
        sortable: true,
        accessor: (g) => (
          <Link
            href={`/games/${g.steam_appid}`}
            className="font-medium text-accent hover:underline"
          >
            {g.name}
          </Link>
        ),
      },
      { key: "steam_appid", header: "AppID", sortable: true },
      {
        key: "genres",
        header: "Genres",
        accessor: (g) =>
          (g.genres ?? "")
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
            .slice(0, 3)
            .join(", ") || "-",
      },
      {
        key: "is_free",
        header: "Free?",
        accessor: (g) => (g.is_free ? "Yes" : "No"),
      },
      { key: "price_text", header: "Price" },
      {
        key: "release_date",
        header: "Released",
        sortable: true,
        accessor: (g) => formatDate(g.release_date),
      },
    ],
    []
  );

  return (
    <div className="flex flex-col gap-3">
      {!embedded && (
        <FilterBar
          filters={filters}
          fields={FILTER_FIELDS}
          onChange={setFilter}
          onReset={() => { reset(); }}
        />
      )}
      <DataTable<Game>
        rows={rows}
        columns={columns}
        rowKey={(g) => g.steam_appid}
        isLoading={isLoading}
        sortBy={filters.sort_by}
        sortDir={filters.sort_order}
        onSortChange={(k, d) => {
          setFilter("sort_by", k as GameFilter["sort_by"]);
          setFilter("sort_order", d);
        }}
        emptyText={isLoading ? "Loading..." : "No games found."}
      />
      <Pagination
        page={filters.page ?? 1}
        pageSize={filters.page_size ?? 20}
        total={total}
        onChange={(p) => setFilter("page", p)}
      />
    </div>
  );
}
