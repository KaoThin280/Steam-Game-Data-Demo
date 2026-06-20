"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { classNames } from "@/utils/format";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onChange: (nextPage: number) => void;
}

export function Pagination({ page, pageSize, total, onChange }: PaginationProps) {
  const lastPage = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);

  const btn = (p: number, label: React.ReactNode, disabled: boolean, key: string) => (
    <button
      key={key}
      onClick={() => onChange(p)}
      disabled={disabled}
      className={classNames(
        "rounded-md border border-white/10 px-2 py-1 text-xs hover:bg-white/5 disabled:opacity-40"
      )}
    >
      {label}
    </button>
  );

  return (
    <div className="flex items-center justify-between gap-2 border-t border-white/5 px-3 py-2 text-xs text-white/60">
      <div>
        {from}-{to} of {total}
      </div>
      <div className="flex items-center gap-1">
        {btn(Math.max(1, page - 1), <ChevronLeft className="h-3.5 w-3.5" />, page <= 1, "prev")}
        <span className="px-2 text-white/60">
          Page {page} / {lastPage}
        </span>
        {btn(Math.min(lastPage, page + 1), <ChevronRight className="h-3.5 w-3.5" />, page >= lastPage, "next")}
      </div>
    </div>
  );
}
