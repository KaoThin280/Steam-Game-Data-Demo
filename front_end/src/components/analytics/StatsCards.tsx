"use client";

import type { ReactNode } from "react";

interface StatCard {
  label: string;
  value: ReactNode;
  hint?: string;
}

export function StatsCards({ cards }: { cards: StatCard[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
      {cards.map((c) => (
        <div
          key={c.label}
          className="rounded-md border border-white/5 bg-bg-soft p-3"
        >
          <div className="text-[11px] uppercase tracking-wide text-white/50">{c.label}</div>
          <div className="mt-1 text-xl font-semibold tabular-nums">{c.value}</div>
          {c.hint && <div className="mt-0.5 text-xs text-white/50">{c.hint}</div>}
        </div>
      ))}
    </div>
  );
}
