/**
 * Loading UI - shown during route transitions (SSR/streaming).
 * Server Component (no "use client" needed).
 */
import { Loader2 } from "lucide-react";

export default function Loading() {
  return (
    <div className="grid h-[60vh] place-items-center">
      <div className="flex items-center gap-3 text-white/40">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span className="text-sm">Đang tải...</span>
      </div>
    </div>
  );
}