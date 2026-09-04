"use client";

import { RotateCcw } from "lucide-react";

import { SearchInput } from "@/components/common/SearchInput";

export interface FilterField {
  key: string;
  label: string;
  type: "search" | "text" | "number" | "select" | "boolean";
  options?: Array<{ value: string; label: string }>;
  placeholder?: string;
}

interface FilterBarProps<T> {
  filters: T;
  fields: FilterField[];
  onChange: <K extends keyof T>(key: K, value: T[K]) => void;
  onReset: () => void;
  className?: string;
}

/**
 * Renders a horizontal filter bar that maps a list of `FilterField`s to inputs
 * bound to a generic `filters` object. Includes a reset button.
 *
 * Usage:
 *   <FilterBar
 *     filters={filters}
 *     fields={[
 *       { key: "search", label: "Search", type: "search" },
 *       { key: "is_free", label: "Free?", type: "boolean" },
 *       { key: "genre", label: "Genre", type: "text" },
 *     ]}
 *     onChange={setFilter}
 *     onReset={reset}
 *   />
 */
export function FilterBar<T extends Record<string, unknown>>({
  filters,
  fields,
  onChange,
  onReset,
  className,
}: FilterBarProps<T>) {
  return (
    <div className={`flex flex-wrap items-end gap-3 rounded-xl border border-line bg-panel p-3 ${className ?? ""}`}>
      {fields.map((f) => {
        const v = filters[f.key];
        const set = (next: unknown) => onChange(f.key as keyof T, next as T[keyof T]);
        return (
          <div key={f.key} className="flex min-w-[160px] flex-col gap-1">
            <label className="text-[11px] uppercase tracking-wide text-muted">{f.label}</label>
            {f.type === "search" && (
              <SearchInput
                value={String(v ?? "")}
                onChange={set}
                placeholder={f.placeholder ?? "Search..."}
              />
            )}
            {f.type === "text" && (
              <input
                type="text"
                value={String(v ?? "")}
                onChange={(e) => set(e.target.value)}
                placeholder={f.placeholder}
                className="rounded-md border border-line bg-bg-soft px-2 py-1.5 text-sm focus:border-accent focus:outline-none"
              />
            )}
            {f.type === "number" && (
              <input
                type="number"
                value={v === undefined || v === null ? "" : String(v)}
                onChange={(e) => set(e.target.value === "" ? undefined : Number(e.target.value))}
                placeholder={f.placeholder}
                className="rounded-md border border-line bg-bg-soft px-2 py-1.5 text-sm focus:border-accent focus:outline-none"
              />
            )}
            {f.type === "select" && (
              <select
                value={String(v ?? "")}
                onChange={(e) => set(e.target.value || undefined)}
                className="rounded-md border border-line bg-bg-soft px-2 py-1.5 text-sm focus:border-accent focus:outline-none"
              >
                <option value="">Any</option>
                {(f.options ?? []).map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            )}
            {f.type === "boolean" && (
              <select
                value={v === undefined ? "" : v ? "true" : "false"}
                onChange={(e) => {
                  if (e.target.value === "") set(undefined);
                  else set(e.target.value === "true");
                }}
                className="rounded-md border border-line bg-bg-soft px-2 py-1.5 text-sm focus:border-accent focus:outline-none"
              >
                <option value="">Any</option>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            )}
          </div>
        );
      })}
      <button
        type="button"
        onClick={onReset}
        className="ml-auto inline-flex items-center gap-1 rounded-md border border-line px-2 py-1.5 text-xs text-muted hover:bg-bg-soft hover:text-fg"
      >
        <RotateCcw className="h-3.5 w-3.5" />
        Reset
      </button>
    </div>
  );
}
