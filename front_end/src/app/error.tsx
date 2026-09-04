"use client";

/**
 * Route-level Error Boundary.
 * Catches errors within a route segment and shows a recovery UI.
 */
import { useEffect } from "react";
import { AlertCircle, RefreshCw, Home } from "lucide-react";
import Link from "next/link";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[RouteError]", error);
  }, [error]);

  return (
    <div className="min-h-[60vh] flex items-center justify-center p-6">
      <div className="max-w-md w-full rounded-lg border border-red-500/20 bg-red-500/5 p-6">
        <div className="flex items-center gap-3 mb-4">
          <AlertCircle className="h-6 w-6 text-red-400" />
          <h2 className="text-lg font-semibold text-white">
            Đã xảy ra lỗi
          </h2>
        </div>
        <p className="text-sm text-white/60 mb-2">
          {error.message || "An unexpected error occurred."}
        </p>
        {error.digest && (
          <p className="text-xs text-white/30 mb-4 font-mono">
            ID: {error.digest}
          </p>
        )}
        <div className="flex gap-3 mt-4">
          <button
            onClick={reset}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-accent text-white text-sm font-medium hover:bg-accent/90 transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
            Thử lại
          </button>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md border border-line text-muted text-sm font-medium hover:bg-bg-soft hover:text-fg transition-colors"
          >
            <Home className="h-4 w-4" />
            Về Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
