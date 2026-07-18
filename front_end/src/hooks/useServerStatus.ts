"use client";

import { useEffect } from "react";

import { useServerStatusStore } from "@/store/serverStatusStore";
import type { ServerStage } from "@/lib/types";

/**
 * Periodically pings a PUBLIC endpoint to check server reachability.
 *
 * Uses `fetch` directly (NOT the axios `api` instance) for two reasons:
 *  1. The ping endpoint doesn't require auth, so we don't want to attach
 *     a Bearer header (which would 401 every time when the user isn't
 *     logged in).
 *  2. We want to bypass the axios interceptors entirely so they don't
 *     emit "fetching" -> "error" stage transitions on every periodic
 *     ping. This prevents the auth store from being re-validated and
 *     avoids the redirect loop between /login and /dashboard.
 *
 * URL resolution:
 *  - In dev: NEXT_PUBLIC_API_URL = http://localhost:8000/api/v1
 *    -> ping goes to http://localhost:8000/ping
 *  - In Vercel prod: NEXT_PUBLIC_API_URL = /api/v1 (relative)
 *    -> ping goes to https://<vercel-host>/api/v1/ping/  (no Vercel rewrite
 *       for /ping, so we instead hit a known public BE endpoint via the
 *       Vercel rewrite. The safest cross-environment check is the
 *       front-end's own /api/v1/health via Vercel rewrite, or a public
 *       endpoint that Vercel rewrites back to the BE.
 *
 * We pick the FRONT-END's `/api/v1/health` (which Vercel rewrites to
 * the BE) so the URL works the same in dev and on Vercel without
 * depending on the BE being reachable over a public IP.
 */
export function useServerStatus() {
  const { stage, detail, lastError, setStage, setError } = useServerStatusStore();

  useEffect(() => {
    let cancelled = false;

    const ping = async () => {
      setStage("connecting");
      try {
        const apiBase =
          process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

        // Resolve to an absolute URL. If the env var is relative (e.g.
        // "/api/v1" on Vercel), combine with window.location.origin.
        let pingUrl: string;
        if (apiBase.startsWith("http://") || apiBase.startsWith("https://")) {
          // Absolute: strip "/api/v1" suffix to get the BE root, then
          // hit "/health" (a public, unauthenticated endpoint).
          pingUrl = apiBase.replace(/\/api\/v1\/?$/, "") + "/health";
        } else {
          // Relative: combine with current origin. Use "/api/v1/health"
          // which is rewritten by Vercel to the BE.
          const origin =
            typeof window !== "undefined" ? window.location.origin : "";
          pingUrl = origin + apiBase.replace(/\/?$/, "") + "/health";
        }

        const res = await fetch(pingUrl, {
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
    // Ping every 60s (purely informational).
    const id = setInterval(ping, 60_000);

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
