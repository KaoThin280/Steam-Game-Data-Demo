"use client";

import { BarChart3, Gamepad2, Languages, RefreshCw, Sparkles } from "lucide-react";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { StatsCards } from "@/components/analytics/StatsCards";
import { ChartRenderer } from "@/components/analytics/ChartRenderer";
import { DataTable } from "@/components/common/DataTable";
import { useGenres, useLanguages, useOverview, useYears } from "@/hooks/useDashboard";
import type { DistributionItem } from "@/lib/types";
import { formatNumber } from "@/utils/format";

export default function DashboardPage() {
  return <RoleGuard allow={["analyst", "scientist", "admin"]}><DashboardView /></RoleGuard>;
}

function DashboardView() {
  const overview = useOverview();
  const genres = useGenres(20);
  const years = useYears(40);
  const languages = useLanguages(15);
  const loading = overview.isLoading || genres.isLoading || years.isLoading || languages.isLoading;
  const refresh = () => Promise.all([overview.mutate(), genres.mutate(), years.mutate(), languages.mutate()]);

  return (
    <div className="mx-auto flex max-w-[1500px] flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-accent/10 px-3 py-1 text-xs font-semibold text-accent"><Sparkles className="h-3.5 w-3.5" /> Live catalogue overview</div>
          <h1 className="text-3xl font-bold tracking-tight text-fg">Steam analytics</h1>
          <p className="mt-1 text-sm text-muted">A clear view of catalogue size, release history and content coverage.</p>
        </div>
        <button onClick={refresh} disabled={loading} className="inline-flex items-center gap-2 rounded-xl border border-line bg-panel px-4 py-2 text-sm font-medium shadow-sm transition hover:border-accent/40 hover:text-accent disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh data</button>
      </header>

      <StatsCards cards={[
        { label: "Total games", value: formatNumber(overview.data?.total_games), hint: "Games in the catalogue" },
        { label: "Free games", value: formatNumber(overview.data?.free_games), hint: "Free-to-play titles" },
        { label: "Paid games", value: formatNumber(overview.data?.paid_games), hint: "Commercial titles" },
        { label: "Developers", value: formatNumber(overview.data?.total_developers), hint: "Unique studios" },
        { label: "Languages", value: formatNumber(overview.data?.total_languages), hint: "Supported languages" },
      ]} />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <ChartCard title="Top genres" subtitle="Games grouped by their primary genres" icon={<BarChart3 className="h-4 w-4" />}>
          <ChartRenderer height={340} spec={{ chart_type: "bar", chart_title: "Genres by game count", x_axis_label: "Genre", y_axis_label: "Games", config: { labels: (genres.data ?? []).slice(0, 12).map((g) => g.genre ?? g.label ?? "Unknown"), datasets: [{ label: "Games", data: (genres.data ?? []).slice(0, 12).map((g) => g.count), borderRadius: 7 }] } }} />
        </ChartCard>
        <ChartCard title="Release history" subtitle="Catalogue growth by release year" icon={<Gamepad2 className="h-4 w-4" />}>
          <ChartRenderer height={340} spec={{ chart_type: "line", chart_title: "Games by release year", x_axis_label: "Year", y_axis_label: "Games", config: { labels: (years.data ?? []).slice().reverse().map((y) => String(y.year ?? y.label ?? "")), datasets: [{ label: "Games", data: (years.data ?? []).slice().reverse().map((y) => y.count), fill: true, tension: 0.25 }] } }} />
        </ChartCard>
        <ChartCard title="Language coverage" subtitle="Most commonly supported languages" icon={<Languages className="h-4 w-4" />} wide>
          <ChartRenderer height={320} spec={{ chart_type: "bar", chart_title: "Languages by supported game count", x_axis_label: "Language", y_axis_label: "Games", config: { labels: (languages.data ?? []).slice(0, 12).map((l) => l.language ?? l.label ?? "Unknown"), datasets: [{ label: "Games", data: (languages.data ?? []).slice(0, 12).map((l) => l.count), borderRadius: 7 }] } }} />
        </ChartCard>
        <div className="overflow-hidden rounded-2xl border border-line bg-panel shadow-sm xl:col-span-2">
          <div className="border-b border-line px-5 py-4"><h2 className="font-semibold text-fg">Genre details</h2><p className="mt-0.5 text-sm text-muted">Exact values behind the genre chart.</p></div>
          <DataTable<DistributionItem> rows={genres.data ?? []} columns={[
            { key: "genre", header: "Genre", accessor: (r) => r.genre ?? r.label ?? "-" },
            { key: "count", header: "Games", accessor: (r) => formatNumber(r.count) },
          ]} rowKey={(r) => `${r.genre ?? r.label}-${r.count}`} isLoading={genres.isLoading} />
        </div>
      </div>
    </div>
  );
}

function ChartCard({ title, subtitle, icon, children, wide = false }: { title: string; subtitle: string; icon: React.ReactNode; children: React.ReactNode; wide?: boolean }) {
  return <section className={`rounded-2xl border border-line bg-panel p-5 shadow-sm ${wide ? "xl:col-span-2" : ""}`}><div className="mb-4 flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-xl bg-accent/10 text-accent">{icon}</span><div><h2 className="font-semibold text-fg">{title}</h2><p className="text-xs text-muted">{subtitle}</p></div></div>{children}</section>;
}
