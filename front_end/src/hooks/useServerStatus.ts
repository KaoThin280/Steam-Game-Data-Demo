"use client";

import { useEffect } from "react";

import { apiGet } from "@/lib/api";
import { useServerStatusStore } from "@/store/serverStatusStore";
import type { ServerStage } from "@/lib/types";

/**
 * Periodically pings /dashboard/overview (light, public, no auth strictly
 * required but the back-end has a protected variant). If the ping succeeds
 * we set stage = connected; otherwise error.
 *
 * Also subscribes to stage changes from axios interceptors (via the store)
 * and exposes a single `useServerStatus()` hook for components.
 */
export function useServerStatus() {
  const { stage, detail, lastError, setStage, setError } = useServerStatusStore();

  useEffect(() => {
    let cancelled = false;
    const ping = async () => {
      setStage("connecting");
      try {
        await apiGet("/dashboard/overview");
        if (!cancelled) setStage("connected");
      } catch (e) {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : "unreachable";
          setError(msg);
        }
      }
    };
    ping();
    const id = setInterval(ping, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [setStage, setError]);

  return { stage, detail, lastError } as {
    stage: ServerStage;
    detail: string | null;
    lastError: string | null;
  };
}
