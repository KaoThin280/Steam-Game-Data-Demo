"use client";

import type { ReactNode } from "react";

interface StatCard {
  label: string;
  value: ReactNode;
  hint?: string;
}

export function StatsCards({ cards }: { cards: StatCard[] }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
      {cards.map((c) => (
        <div
          key={c.label}
          className="rounded-2xl border border-line bg-panel p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
        >
          <div className="text-[11px] font-semibold uppercase tracking-[.12em] text-muted">{c.label}</div>
          <div className="mt-2 text-2xl font-semibold tabular-nums text-fg">{c.value}</div>
          {c.hint && <div className="mt-1 text-xs text-muted">{c.hint}</div>}
        </div>
      ))}
    </div>
  );
}
