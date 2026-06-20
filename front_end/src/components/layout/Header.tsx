"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut, User as UserIcon } from "lucide-react";

import { useAuth } from "@/hooks/useAuth";
import { ROLE_LABELS } from "@/utils/permissions";
import { ServerStatusBadge } from "@/components/layout/ServerStatusBadge";

export function Header() {
  const { user, logout } = useAuth();
  const router = useRouter();

  const onLogout = async () => {
    await logout();
    router.replace("/login");
  };

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-white/5 bg-bg/95 px-4 backdrop-blur">
      <div className="flex items-center gap-4">
        <Link href="/" className="text-sm font-semibold tracking-tight">
          Steam Game Data
        </Link>
        <ServerStatusBadge />
      </div>
      <div className="flex items-center gap-3">
        {user ? (
          <>
            <div className="hidden text-right text-xs leading-tight sm:block">
              <div className="font-medium">{user.full_name || user.username}</div>
              <div className="text-white/50">
                {(user.roles || []).map((r) => ROLE_LABELS[r]).join(", ")}
              </div>
            </div>
            <button
              onClick={onLogout}
              className="inline-flex items-center gap-1 rounded-md border border-white/10 px-2 py-1 text-xs hover:bg-white/5"
              aria-label="Logout"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Logout</span>
            </button>
          </>
        ) : (
          <Link
            href="/login"
            className="inline-flex items-center gap-1 rounded-md border border-white/10 px-2 py-1 text-xs hover:bg-white/5"
          >
            <UserIcon className="h-3.5 w-3.5" />
            <span>Login</span>
          </Link>
        )}
      </div>
    </header>
  );
}
