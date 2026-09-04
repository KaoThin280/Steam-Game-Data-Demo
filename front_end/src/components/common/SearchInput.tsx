"use client";

import { Search } from "lucide-react";

interface SearchInputProps {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  className?: string;
}

export function SearchInput({
  value,
  onChange,
  placeholder = "Search...",
  className,
}: SearchInputProps) {
  return (
    <div className={`relative ${className ?? ""}`}>
      <Search className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md border border-line bg-bg-soft py-1.5 pl-8 pr-3 text-sm placeholder:text-muted focus:border-accent focus:outline-none"
      />
    </div>
  );
}
