"use client";

import { useState } from "react";
import { BarChart3, Gamepad2, Users } from "lucide-react";

import { RoleGuard } from "@/components/auth/RoleGuard";
import { StatsCards } from "@/components/analytics/StatsCards";
import { ChartRenderer } from "@/components/analytics/ChartRenderer";
import { DataTable, type Column } from "@/components/common/DataTable";
import { ChatWindow } from "@/components/chat/ChatWindow";
import {
  useGenres,
  useLanguages,
  useOverview,
  useYears,
} from "@/hooks/useDashboard";
import type { DistributionItem } from "@/lib/types";
import { formatNumber } from "@/utils/format";

type Tab = "games" | "users";

export default function DashboardPage() {
  return (
    <RoleGuard allow={["analyst", "scientist", "admin"]}>
      <DashboardView />
    </RoleGuard>
  );
}

function DashboardView() {
  const [tab, setTab] = useState<Tab>("games");

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
      <section className="flex min-w-0 flex-col gap-4">
        <header className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h1 className="text-2xl font-semibold">Dashboard</h1>
            <p className="text-sm text-white/60">
              Quick stats and charts. Use the chat panel to ask deeper
              questions or run Python on the data.
            </p>
          </div>
          <nav className="flex items-center gap-1 rounded-md border border-white/10 bg-bg-soft p-1 text-sm">
            <TabButton active={tab === "games"} onClick={() => setTab("games")} icon={<Gamepad2 className="h-4 w-4" />} label="Games" />
            <TabButton active={tab === "users"} onClick={() => setTab("users")} icon={<Users className="h-4 w-4" />} label="Steam Users" />
          </nav>
        </header>

        {tab === "games" ? <GamesTab /> : <UsersTab />}
      </section>

      <aside className="min-h-[640px] xl:sticky xl:top-16 xl:h-[calc(100vh-4rem)]">
        <ChatWindow />
      </aside>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "inline-flex items-center gap-1 rounded-md px-3 py-1.5 " +
        (active
          ? "bg-accent/20 text-accent"
          : "text-white/70 hover:bg-white/5")
      }
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

// ---------- Games tab ----------
function GamesTab() {
  const overview = useOverview();
  const genres = useGenres(20);
  const years = useYears(30);
  const languages = useLanguages(15);

  return (
    <>
      <StatsCards
        cards={[
          { label: "Total games", value: formatNumber(overview.data?.total_games), hint: "rows in public.games" },
          { label: "Free games", value: formatNumber(overview.data?.free_games) },
          { label: "Paid games", value: formatNumber(overview.data?.paid_games) },
          { label: "Developers", value: formatNumber(overview.data?.total_developers) },
          { label: "Supported languages", value: formatNumber(overview.data?.total_languages) },
        ]}
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Top genres">
          <ChartRenderer
            height={300}
            spec={{
              chart_type: "bar",
              chart_title: "Genres by game count",
              x_axis_label: "Genre",
              y_axis_label: "Games",
              config: {
                  labels: (genres.data ?? []).slice(0, 15).map((g) => g.genre ?? g.label ?? "Unknown"),
                  datasets: [
                    {
                      label: "Games",
                      data: (genres.data ?? []).slice(0, 15).map((g) => g.count),
                  },
                ],
              },
            }}
          />
        </Card>
        <Card title="Games by release year">
          <ChartRenderer
            height={300}
            spec={{
              chart_type: "line",
              chart_title: "Release year distribution",
              x_axis_label: "Year",
              y_axis_label: "Games",
              config: {
                labels: (years.data ?? [])
                  .slice()
                  .reverse()
                  .map((y) => String(y.year ?? y.label ?? "")),
                datasets: [
                  {
                    label: "Games",
                    data: (years.data ?? [])
                      .slice()
                      .reverse()
                      .map((y) => y.count),
                  },
                ],
              },
            }}
          />
        </Card>
        <Card title="Top languages" wide>
          <ChartRenderer
            height={260}
            spec={{
              chart_type: "doughnut",
              chart_title: "Languages by supported game count",
              config: {
                  labels: (languages.data ?? []).slice(0, 10).map((l) => l.language ?? l.label ?? ""),
                  datasets: [
                    {
                      label: "Games",
                      data: (languages.data ?? []).slice(0, 10).map((l) => l.count),
                  },
                ],
              },
            }}
          />
        </Card>
        <Card title="Genre table" wide>
          <DataTable<DistributionItem>
            rows={genres.data ?? []}
            columns={[
              { key: "genre", header: "Genre", accessor: (r) => r.genre ?? r.label ?? "-" },
              { key: "count", header: "Games", accessor: (r) => formatNumber(r.count) },
            ]}
            rowKey={(r) => `${r.genre ?? r.label}-${r.count}`}
            isLoading={genres.isLoading}
          />
        </Card>
      </div>
    </>
  );
}

// ---------- Steam Users tab (placeholder data; full implementation
//   will use /dashboard/users endpoints when added). ----------
function UsersTab() {
  // Reuse /dashboard/languages as a quick demo; replace with /dashboard/users once available.
  const languages = useLanguages(15);
  return (
    <>
      <StatsCards
        cards={[
          { label: "Total reviews", value: "Coming soon" },
          { label: "Unique reviewers", value: "Coming soon" },
          { label: "Avg playtime", value: "Coming soon" },
          { label: "Top language", value: "Coming soon" },
        ]}
      />
      <Card title="Steam users (preview)">
        <p className="text-sm text-white/60">
          This tab will visualise Steam reviewer demographics. While the dedicated
          /dashboard/users endpoints are not yet implemented, the chart below
          reuses the language distribution to demonstrate the layout.
        </p>
        <div className="mt-3">
          <ChartRenderer
            height={300}
            spec={{
              chart_type: "bar",
              chart_title: "Review languages (preview)",
              x_axis_label: "Language",
              y_axis_label: "Games",
              config: {
                  labels: (languages.data ?? []).slice(0, 10).map((l) => l.language ?? l.label ?? ""),
                datasets: [
                  {
                    label: "Games",
                    data: (languages.data ?? []).slice(0, 10).map((l) => l.count),
                  },
                ],
              },
            }}
          />
        </div>
      </Card>
    </>
  );
}

function Card({
  title,
  children,
  wide = false,
}: {
  title: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div className={"rounded-md border border-white/5 bg-bg-soft p-3 " + (wide ? "lg:col-span-2" : "")}>
      <h2 className="mb-2 flex items-center gap-2 text-sm font-medium text-white/80">
        <BarChart3 className="h-3.5 w-3.5" />
        {title}
      </h2>
      {children}
    </div>
  );
}
