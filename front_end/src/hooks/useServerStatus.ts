"use client";

import { useEffect } from "react";

import { useServerStatusStore } from "@/store/serverStatusStore";
import type { ServerStage } from "@/lib/types";

/**
 * Periodically pings a PUBLIC endpoint (/ping) to check server reachability.
 *
 * Uses `fetch` directly (NOT the axios `api` instance) for two reasons:
 *  1. /ping doesn't require auth, so we don't want to attach a Bearer header
 *     (which would 401 every time when the user isn't logged in).
 *  2. We want to bypass the axios interceptors entirely so they don't emit
 *     "fetching" -> "error" stage transitions on every ping. This prevents
 *     the auth store from being re-validated and avoids the redirect loop
 *     between /login and /dashboard.
 */
export function useServerStatus() {
  const { stage, detail, lastError, setStage, setError } = useServerStatusStore();

  useEffect(() => {
    let cancelled = false;

    const ping = async () => {
      setStage("connecting");
      try {
        // Hit the public /ping endpoint on the back-end (no /api/v1 prefix).
        // baseURL already includes /api/v1; strip it to call /ping at the root.
        const apiBase =
          process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
        const rootBase = apiBase.replace(/\/api\/v1\/?$/, "");
        const res = await fetch(`${rootBase}/ping`, {
          method: "GET",
          cache: "no-store",
        });
        if (!cancelled) {
          if (res.ok) setStage("connected");
          else setError(`HTTP ${res.status}`);
        }
      } catch (e) {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : "unreachable";
          setError(msg);
        }
      }
    };

    ping();
    // Increase interval to 60s to reduce noise; ping is purely informational.
    const id = setInterval(ping, 60_000);

    return () => {
      cancelled = true;
      clearInterval(id);
    };
    // setStage / setError are stable zustand setters, but include them for
    // exhaustive-deps correctness.
  }, [setStage, setError]);

  return { stage, detail, lastError } as {
    stage: ServerStage;
    detail: string | null;
    lastError: string | null;
  };
}
