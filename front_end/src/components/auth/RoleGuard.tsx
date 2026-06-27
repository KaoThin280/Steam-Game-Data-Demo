"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

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

/**
 * Client-side role gate. Redirects to `/login` (or `fallback`) when the
 * current user is not authenticated or does not have any of the allowed
 * roles. Renders a small placeholder while hydrating so we don't flash
 * protected UI for an unauthenticated visitor.
 */
export function RoleGuard({ allow, fallback = "/login", children }: RoleGuardProps) {
  const { hydrated, isAuthenticated, user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!hydrated) return;
    if (!isAuthenticated) {
      router.replace(fallback);
      return;
    }
    // user is still loading (token exists but /auth/me hasn't returned yet)
    if (!user) return;
    if (!userHasAnyRole(user?.roles, ...allow)) {
      router.replace("/");
    }
  }, [hydrated, isAuthenticated, user, allow, fallback, router]);

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
  // Still waiting for /auth/me to complete
  if (!user) {
    return (
      <div className="grid h-[40vh] place-items-center text-sm text-white/60">
        Loading user profile...
      </div>
    );
  }
  if (!userHasAnyRole(user?.roles, ...allow)) {
    return (
      <div className="grid h-[40vh] place-items-center text-sm text-white/60">
        Redirecting...
      </div>
    );
  }

  return <>{children}</>;
}
