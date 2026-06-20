"use client";

import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";

import { RoleGuard } from "@/components/auth/RoleGuard";
import { DataTable, type Column } from "@/components/common/DataTable";
import { apiGet } from "@/lib/api";

interface AdminUser {
  id: number;
  username: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  roles: string[];
}

export default function AdminPage() {
  return (
    <RoleGuard allow={["admin"]}>
      <AdminView />
    </RoleGuard>
  );
}

function AdminView() {
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiGet<AdminUser[]>("/admin/users")
      .then(setUsers)
      .catch((e) => setErr(e instanceof Error ? e.message : "Failed"));
  }, []);

  const columns: Column<AdminUser>[] = [
    { key: "id", header: "ID" },
    { key: "username", header: "Username" },
    { key: "email", header: "Email" },
    {
      key: "full_name",
      header: "Full name",
      accessor: (u) => u.full_name ?? "-",
    },
    {
      key: "is_active",
      header: "Active?",
      accessor: (u) => (u.is_active ? "Yes" : "No"),
    },
    {
      key: "roles",
      header: "Roles",
      accessor: (u) => u.roles.join(", ") || "-",
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          <ShieldCheck className="h-5 w-5" />
          Administration
        </h1>
        <p className="text-sm text-white/60">
          Manage users, roles, and database records. This page only lists
          accounts; full CRUD will follow once /admin endpoints are stable.
        </p>
      </header>
      {err && (
        <div className="rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
          {err}
        </div>
      )}
      <DataTable<AdminUser>
        rows={users ?? []}
        columns={columns}
        rowKey={(u) => u.id}
        isLoading={users === null && !err}
        emptyText={err ? "Failed to load users." : "No users."}
      />
    </div>
  );
}
