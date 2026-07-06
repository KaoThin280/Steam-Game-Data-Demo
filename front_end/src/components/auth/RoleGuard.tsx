"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

import { useAuth } from "@/hooks/useAuth";
import { userHasAnyRole } from "@/utils/permissions";
import type { RoleName } from "@/lib/types";

interface RoleGuardProps {
  /** Any of these roles may view the wrapped children. */
  allow: RoleName[];
  /** Where to redirect when the guard fails. Defaults to /login. */
  fallback?: string;
  children: React.ReactNode;
}

const DEBUG = false;

/**
 * Client-side role gate. Redirects to `/login` (or `fallback`) when the
 * current user is not authenticated. Redirects authenticated users with
 * the wrong role to a page they CAN access (their default landing page)
 * instead of bouncing them to `/` (which would cause a redirect loop).
 *
 * Notes:
 *  - The router is held in a ref so it doesn't trigger the effect to
 *    re-run on every render (Next.js returns a new object each time).
 *  - The redirect is fired at most once per "decision change" so the
 *    guard does not fight with the router while navigation is pending.
 */
export function RoleGuard({ allow, fallback = "/login", children }: RoleGuardProps) {
  const { hydrated, isAuthenticated, user } = useAuth();
  const router = useRouter();
  // Hold the latest values in refs so the effect's identity is stable.
  const routerRef = useRef(router);
  routerRef.current = router;

  const allowRef = useRef(allow);
  allowRef.current = allow;

  const fallbackRef = useRef(fallback);
  fallbackRef.current = fallback;

  const redirectedTo = useRef<string | null>(null);

  useEffect(() => {
    if (!hydrated) {
      if (DEBUG) console.log("[RoleGuard] not hydrated, wait");
      return;
    }

    // 1) Not authenticated -> go to login.
    if (!isAuthenticated) {
      const target = fallbackRef.current;
      if (redirectedTo.current !== target) {
        if (DEBUG) console.log("[RoleGuard] not authenticated ->", target);
        redirectedTo.current = target;
        routerRef.current.replace(target);
      }
      return;
    }

    // 2) Authenticated but /auth/me hasn't returned yet -> wait.
    if (!user) {
      if (DEBUG) console.log("[RoleGuard] authed but no user yet, wait");
      return;
    }

    // 3) Authenticated AND user loaded: check role.
    if (userHasAnyRole(user.roles, ...allowRef.current)) {
      if (DEBUG) console.log("[RoleGuard] allowed, render children. user.roles=", user.roles);
      // Reset so a future allow[] change can fire a redirect.
      redirectedTo.current = null;
      return;
    }

    // 4) Wrong role - send them somewhere they CAN access.
    const isAnalyst =
      userHasAnyRole(user.roles, "analyst", "scientist", "admin");
    const target = isAnalyst ? "/dashboard" : "/games";
    if (DEBUG) console.log("[RoleGuard] wrong role, redirect to", target);
    if (redirectedTo.current !== target) {
      redirectedTo.current = target;
      routerRef.current.replace(target);
    }
    // We deliberately exclude `router`, `allow`, and `fallback` from the
    // dependency list - their values are read through refs to avoid
    // re-running the effect on every parent re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated, isAuthenticated, user]);

  if (!hydrated) {
    return (
      <div className="grid h-[40vh] place-items-center text-sm text-white/60">
        Checking permissions...
      </div>
    );
  }
  if (!isAuthenticated) {
    return (
      <div className="grid h-[40vh] place-items-center text-sm text-white/60">
        Redirecting to login...
      </div>
    );
  }
  if (!user) {
    return (
      <div className="grid h-[40vh] place-items-center text-sm text-white/60">
        Loading user profile...
      </div>
    );
  }
  if (!userHasAnyRole(user.roles, ...allow)) {
    return (
      <div className="grid h-[40vh] place-items-center text-sm text-white/60">
        Redirecting...
      </div>
    );
  }

  return <>{children}</>;
}
