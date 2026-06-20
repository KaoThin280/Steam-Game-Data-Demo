"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Gamepad2,
  Home,
  MessageSquare,
  ShieldCheck,
  Users,
} from "lucide-react";

import { useAuth } from "@/hooks/useAuth";
import { canUseAnalystChat, userHasAnyRole } from "@/utils/permissions";
import { classNames } from "@/utils/format";
import type { RoleName } from "@/lib/types";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  roles: RoleName[];
}

const NAV: NavItem[] = [
  { href: "/games",       label: "Games",       icon: Gamepad2,     roles: ["viewer", "analyst", "scientist", "admin"] },
  { href: "/dashboard",   label: "Dashboard",   icon: BarChart3,    roles: ["analyst", "scientist", "admin"] },
  { href: "/chat",        label: "AI Chat",     icon: MessageSquare, roles: ["analyst", "scientist", "admin"] },
  { href: "/users",       label: "Steam Users", icon: Users,        roles: ["analyst", "scientist", "admin"] },
  { href: "/admin",       label: "Admin",       icon: ShieldCheck,  roles: ["admin"] },
];

export function Sidebar() {
  const { user } = useAuth();
  const pathname = usePathname();
  const roles = user?.roles;
  const showChat = canUseAnalystChat(roles);

  return (
    <aside className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-56 shrink-0 border-r border-white/5 bg-bg-soft p-3 lg:block">
      <nav className="flex flex-col gap-1 text-sm">
        <Link
          href="/"
          className={classNames(
            "flex items-center gap-2 rounded-md px-3 py-2 hover:bg-white/5",
            pathname === "/" && "bg-white/5"
          )}
        >
          <Home className="h-4 w-4" />
          <span>Home</span>
        </Link>

        {NAV.map((item) => {
          if (item.label === "AI Chat" && !showChat) return null;
          if (!userHasAnyRole(roles, ...item.roles)) return null;
          const active = pathname?.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={classNames(
                "flex items-center gap-2 rounded-md px-3 py-2 hover:bg-white/5",
                active && "bg-white/10 text-white"
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
