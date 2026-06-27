"use client";

import { useMemo } from "react";

import { FilterBar, type FilterField } from "@/components/common/FilterBar";
import { Pagination } from "@/components/common/Pagination";
import { DataTable, type Column } from "@/components/common/DataTable";
import { useFilters } from "@/hooks/useFilters";
import { useGame, useReviews } from "@/hooks/useGames";
import type { Game, Review, ReviewFilter } from "@/lib/types";
import { formatDate, formatNumber } from "@/utils/format";

const REVIEW_FILTERS: FilterField[] = [
  { key: "language", label: "Language", type: "text", placeholder: "e.g. english" },
  { key: "refunded", label: "Refunded?", type: "boolean" },
  { key: "received_for_free", label: "Received free?", type: "boolean" },
  { key: "primarily_steam_deck", label: "Played on Deck?", type: "boolean" },
  { key: "min_playtime_forever", label: "Min playtime (min)", type: "number" },
];

export function GameDetailPanel({ appid }: { appid: number }) {
  const { data: game, isLoading } = useGame(appid);
  const { filters, setFilter, reset } = useFilters<ReviewFilter>({
    page: 1,
    page_size: 20,
  });
  const { data: revData, isLoading: revLoading } = useReviews(appid, filters);
  const reviews = revData?.items ?? [];
  const total = revData?.total ?? 0;

  const columns: Column<Review>[] = useMemo(
    () => [
      {
        key: "review_text",
        header: "Review",
        accessor: (r) => (
          <div className="max-w-[640px] whitespace-pre-wrap text-sm leading-relaxed">
            {r.review_text || <span className="text-white/40">(empty)</span>}
          </div>
        ),
      },
      { key: "language", header: "Lang" },
      {
        key: "playtime_forever",
        header: "Playtime",
        accessor: (r) => `${formatNumber(r.playtime_forever)} min`,
      },
      {
        key: "timestamp_created",
        header: "Date",
        accessor: (r) => formatDate(r.timestamp_created),
      },
    ],
    []
  );

  if (isLoading) return <div className="p-6 text-white/60">Loading game...</div>;
  if (!game) return <div className="p-6 text-white/60">Game not found.</div>;

  return (
    <div className="flex flex-col gap-6">
      <GameHeader game={game} />
      <section>
        <h2 className="mb-2 text-lg font-semibold">Reviews</h2>
        <FilterBar
          filters={filters as any}
          fields={REVIEW_FILTERS}
          onChange={setFilter}
          onReset={reset}
        />
        <div className="mt-3">
          <DataTable<Review>
            rows={reviews}
            columns={columns}
            rowKey={(r) => r.recommendationid}
            isLoading={revLoading}
            emptyText="No reviews match the current filters."
          />
          <Pagination
            page={filters.page ?? 1}
            pageSize={filters.page_size ?? 20}
            total={total}
            onChange={(p) => setFilter("page", p)}
          />
        </div>
      </section>
    </div>
  );
}

function GameHeader({ game }: { game: Game }) {
  const splitCsv = (s: string | null | undefined): string[] =>
    (s ?? "").split(",").map((x) => x.trim()).filter(Boolean);

  return (
    <header className="rounded-md border border-white/5 bg-bg-soft p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">{game.name}</h1>
        <div className="text-xs text-white/50">AppID {game.steam_appid}</div>
      </div>
      <dl className="mt-3 grid grid-cols-1 gap-2 text-sm md:grid-cols-3">
        <Pair label="Released" value={formatDate(game.release_date)} />
        <Pair label="Price" value={game.price_text || (game.is_free ? "Free" : "-")} />
        <Pair label="Required age" value={String(game.required_age)} />
        <Pair label="Developers" value={splitCsv(game.developers).join(", ") || "-"} />
        <Pair label="Publishers" value={splitCsv(game.publishers).join(", ") || "-"} />
      </dl>
    </header>
  );
}

function Pair({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-white/50">{label}</dt>
      <dd className="text-white/90">{value}</dd>
    </div>
  );
}
