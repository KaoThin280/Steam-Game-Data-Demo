"use client";

import useSWR from "swr";

import { apiGet } from "@/lib/api";
import type { DistributionItem, OverviewStats } from "@/lib/types";

export function useOverview() {
  return useSWR<OverviewStats>("/dashboard/overview", (u) =>
    apiGet<OverviewStats>(u)
  );
}

export function useTopGames(limit = 10) {
  return useSWR<{ items: Array<{ steam_appid: number; name: string; total_reviews: number }> }>(
    ["/dashboard/top-games", limit],
    ([u, l]) => apiGet<typeof itemsDefault>(u, { limit: l })
  );
}

const itemsDefault = { items: [] as Array<{ steam_appid: number; name: string; total_reviews: number }> };

export function useGenres(limit = 20) {
  return useSWR<DistributionItem[]>(["/dashboard/genres", limit], ([u, l]) =>
    apiGet<DistributionItem[]>(u, { limit: l })
  );
}

export function useYears(limit = 30) {
  return useSWR<DistributionItem[]>(["/dashboard/years", limit], ([u, l]) =>
    apiGet<DistributionItem[]>(u, { limit: l })
  );
}

export function useLanguages(limit = 15) {
  return useSWR<DistributionItem[]>(["/dashboard/languages", limit], ([u, l]) =>
    apiGet<DistributionItem[]>(u, { limit: l })
  );
}
