"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut, Moon, Sun, User as UserIcon } from "lucide-react";

import { useAuth } from "@/hooks/useAuth";
import { ROLE_LABELS } from "@/utils/permissions";
import { ServerStatusBadge } from "@/components/layout/ServerStatusBadge";
import { useTheme } from "@/components/layout/ThemeProvider";

export function Header() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const { theme, toggleTheme } = useTheme();

  const onLogout = async () => {
    await logout();
    router.replace("/login");
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-line bg-panel/90 px-4 shadow-sm backdrop-blur md:px-6">
      <div className="flex items-center gap-4">
        <Link href="/" className="text-sm font-semibold tracking-tight">
          Steam Game Data
        </Link>
        <ServerStatusBadge />
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={toggleTheme}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-panel text-muted transition hover:border-accent/40 hover:text-accent"
          aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
          title={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
        >
          {theme === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
        </button>
        {user ? (
          <>
            <div className="hidden text-right text-xs leading-tight sm:block">
              <div className="font-medium">{user.full_name || user.username}</div>
              <div className="text-muted">
                {(user.roles || []).map((r) => ROLE_LABELS[r]).join(", ")}
              </div>
            </div>
            <button
              onClick={onLogout}
              className="inline-flex items-center gap-1 rounded-lg border border-line px-3 py-2 text-xs hover:bg-bg-soft"
              aria-label="Logout"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Logout</span>
            </button>
          </>
        ) : (
          <Link
            href="/login"
            className="inline-flex items-center gap-1 rounded-lg border border-line px-3 py-2 text-xs hover:bg-bg-soft"
          >
            <UserIcon className="h-3.5 w-3.5" />
            <span>Login</span>
          </Link>
        )}
      </div>
    </header>
  );
}
