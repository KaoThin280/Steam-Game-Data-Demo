"use client";

import { useServerStatus } from "@/hooks/useServerStatus";

/**
 * Mounts the periodic BE ping so the ServerStatusBadge has live data.
 * Lives in its own file (and its own client boundary) so the root layout
 * can stay a Server Component.
 */
export function ServerStatusBoot() {
  useServerStatus();
  return null;
}
