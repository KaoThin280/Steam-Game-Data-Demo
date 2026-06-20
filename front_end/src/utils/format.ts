/**
 * Small formatting helpers used across pages.
 */

export const formatNumber = (n: number | null | undefined): string => {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return n.toLocaleString();
};

export const formatPercent = (n: number, total: number): string => {
  if (!total) return "0%";
  return `${((n / total) * 100).toFixed(1)}%`;
};

export const formatDate = (iso: string | null | undefined): string => {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleDateString();
};

export const formatDateTime = (iso: string | null | undefined): string => {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleString();
};

export const truncate = (s: string, n = 240): string =>
  s.length <= n ? s : `${s.slice(0, n)}... [+${s.length - n}]`;

export const classNames = (...parts: Array<string | false | undefined | null>): string =>
  parts.filter(Boolean).join(" ");
