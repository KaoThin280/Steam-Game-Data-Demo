"use client";

import { useEffect } from "react";

import { useServerStatusStore } from "@/store/serverStatusStore";
import type { ServerStage } from "@/lib/types";

/**
 * Server status hook.
 *
 * Health-check pings have been disabled to avoid background network
 * traffic. The badge will simply show "connected" once the app has
 * hydrated. (Re-enable a periodic ping here if you ever need liveness
 * signals for ops dashboards.)
 */
export function useServerStatus() {
  const { stage, detail, lastError, setStage } = useServerStatusStore();

  useEffect(() => {
    // Mark as connected on mount; no network calls.
    setStage("connected");
  }, [setStage]);

  return { stage, detail, lastError } as {
    stage: ServerStage;
    detail: string | null;
    lastError: string | null;
  };
}
