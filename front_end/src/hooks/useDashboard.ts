"use client";

import useSWR from "swr";

import { apiGet } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import type { DistributionItem, OverviewStats } from "@/lib/types";

function useAuthenticated() {
  const accessToken = useAuthStore((s) => s.accessToken);
  return !!accessToken;
}

const SWR_OPTS = {
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
  dedupingInterval: 30_000,
};

/** SWR fetcher that only fires when the user is authenticated. */
function authFetcher<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const authenticated = useAuthStore.getState().accessToken;
  if (!authenticated) {
    // Return a never-resolving promise so SWR doesn't send the request
    return new Promise<T>(() => {});
  }
  return apiGet<T>(url, params);
}

export function useOverview() {
  const authed = useAuthenticated();
  return useSWR<OverviewStats>(
    authed ? "/dashboard/overview" : null,
    (u) => apiGet<OverviewStats>(u),
    SWR_OPTS
  );
}

export function useTopGames(limit = 10) {
  const authed = useAuthenticated();
  return useSWR<{ items: Array<{ steam_appid: number; name: string; total_reviews: number }> }>(
    authed ? ["/dashboard/top-games", limit] : null,
    ([u, l]) => apiGet<typeof itemsDefault>(u, { limit: l }),
    SWR_OPTS
  );
}

const itemsDefault = { items: [] as Array<{ steam_appid: number; name: string; total_reviews: number }> };

export function useGenres(limit = 20) {
  const authed = useAuthenticated();
  return useSWR<DistributionItem[]>(
    authed ? ["/dashboard/genres", limit] : null,
    ([u, l]) => apiGet<DistributionItem[]>(u, { limit: l }),
    SWR_OPTS
  );
}

export function useYears(limit = 30) {
  const authed = useAuthenticated();
  return useSWR<DistributionItem[]>(
    authed ? ["/dashboard/years", limit] : null,
    ([u, l]) => apiGet<DistributionItem[]>(u, { limit: l }),
    SWR_OPTS
  );
}

export function useLanguages(limit = 15) {
  const authed = useAuthenticated();
  return useSWR<DistributionItem[]>(
    authed ? ["/dashboard/languages", limit] : null,
    ([u, l]) => apiGet<DistributionItem[]>(u, { limit: l }),
    SWR_OPTS
  );
}
