"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

import { useAuth } from "@/hooks/useAuth";
import { canUseAnalystChat } from "@/utils/permissions";

/**
 * Root entry: redirect to the right page for the current user.
 *  - not authenticated -> /login
 *  - analyst/scientist/admin -> /dashboard
 *  - viewer -> /games
 *
 * Tracks the last target we tried so we don't fire the same redirect
 * on every re-render (which causes a "Loading..." flash).
 */
export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, hydrated, user } = useAuth();
  const redirectedTo = useRef<string | null>(null);

  useEffect(() => {
    if (!hydrated) return;

    // Wait until we know who the user is.
    if (isAuthenticated && !user) return;

    let target: string;
    if (!isAuthenticated) {
      target = "/login";
    } else if (canUseAnalystChat(user?.roles)) {
      target = "/dashboard";
    } else {
      target = "/games";
    }

    if (redirectedTo.current === target) return;
    redirectedTo.current = target;
    router.replace(target);
  }, [hydrated, isAuthenticated, user, router]);

  return (
    <div className="grid h-[60vh] place-items-center text-sm text-white/60">
      Loading...
    </div>
  );
}
