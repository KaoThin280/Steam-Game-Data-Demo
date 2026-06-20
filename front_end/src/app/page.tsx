"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/hooks/useAuth";
import { canUseAnalystChat } from "@/utils/permissions";

/**
 * Root entry: redirect to the right page for the current user.
 *  - not authenticated -> /login
 *  - analyst/scientist/admin -> /dashboard
 *  - viewer -> /games
 */
export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, hydrated, user } = useAuth();

  useEffect(() => {
    if (!hydrated) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (canUseAnalystChat(user?.roles)) {
      router.replace("/dashboard");
    } else {
      router.replace("/games");
    }
  }, [hydrated, isAuthenticated, user, router]);

  return (
    <div className="grid h-[60vh] place-items-center text-sm text-white/60">
      Loading...
    </div>
  );
}
