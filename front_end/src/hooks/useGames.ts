"use client";

import useSWR from "swr";

import { apiGet } from "@/lib/api";
import type {
  Game,
  GameFilter,
  PaginatedResponse,
  Review,
  ReviewFilter,
} from "@/lib/types";

/** Build a deterministic SWR cache key from a filter object. */
const serialize = (obj: Record<string, unknown> | undefined) =>
  obj ? JSON.stringify(obj) : "";

export function useGames(filter: GameFilter | undefined) {
  const key = filter ? ["/games", serialize(filter)] : null;
  return useSWR<PaginatedResponse<Game>>(key, async ([url, _]) => {
    const params: Record<string, unknown> = {};
    if (filter?.search) params.search = filter.search;
    if (filter?.genre) params.genre = filter.genre;
    if (filter?.category) params.category = filter.category;
    if (filter?.developer) params.developer = filter.developer;
    if (filter?.publisher) params.publisher = filter.publisher;
    if (filter?.is_free !== undefined) params.is_free = filter.is_free;
    if (filter?.year !== undefined) params.year = filter.year;
    if (filter?.sort_by) params.sort_by = filter.sort_by;
    if (filter?.sort_order) params.sort_order = filter.sort_order;
    params.page = filter?.page ?? 1;
    params.page_size = filter?.page_size ?? 20;
    return apiGet<PaginatedResponse<Game>>(url as string, params);
  });
}

export function useGame(appid: number | null) {
  return useSWR<Game>(appid ? `/games/${appid}` : null, (url) =>
    apiGet<Game>(url)
  );
}

export function useReviews(appid: number | null, filter: ReviewFilter | undefined) {
  const key = appid ? [`/games/${appid}/reviews`, serialize(filter)] : null;
  return useSWR<PaginatedResponse<Review>>(key, async ([url, _]) => {
    const params: Record<string, unknown> = {};
    if (filter?.language) params.language = filter.language;
    if (filter?.refunded !== undefined) params.refunded = filter.refunded;
    if (filter?.received_for_free !== undefined)
      params.received_for_free = filter.received_for_free;
    if (filter?.primarily_steam_deck !== undefined)
      params.primarily_steam_deck = filter.primarily_steam_deck;
    if (filter?.min_playtime_forever !== undefined)
      params.min_playtime_forever = filter.min_playtime_forever;
    params.page = filter?.page ?? 1;
    params.page_size = filter?.page_size ?? 20;
    return apiGet<PaginatedResponse<Review>>(url as string, params);
  });
}
