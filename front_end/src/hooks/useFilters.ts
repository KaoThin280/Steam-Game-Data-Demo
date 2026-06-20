"use client";

import { useCallback, useMemo, useState } from "react";

/**
 * Generic filter state hook.
 * - `filters` is the current object
 * - `setFilter(key, value)` updates one field
 * - `reset()` clears all fields
 * - `queryString` produces a stable URLSearchParams snapshot
 */
export function useFilters<T extends object>(initial: T) {
  const [filters, setFilters] = useState<T>(initial);

  const setFilter = useCallback(<K extends keyof T>(key: K, value: T[K]) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }, []);

  const reset = useCallback(() => setFilters(initial), [initial]);

  const queryString = useMemo(() => {
    const usp = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v === undefined || v === null || v === "") return;
      usp.set(k, String(v));
    });
    return usp;
  }, [filters]);

  return { filters, setFilter, reset, queryString };
}
