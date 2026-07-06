"use client";

/**
 * Global Error Boundary - catches errors that escape route error.tsx.
 * This is required by Next.js App Router for root-level errors.
 */
import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log to console (in production, send to monitoring service)
    console.error("[GlobalError]", error);
  }, [error]);

  return (
    <html lang="en">
      <body className="min-h-screen bg-bg text-white flex items-center justify-center">
        <div className="max-w-md w-full p-6 rounded-lg border border-red-500/20 bg-red-500/5">
          <h2 className="text-lg font-semibold text-red-300 mb-2">
            Something went wrong!
          </h2>
          <p className="text-sm text-white/60 mb-4">
            An unexpected error occurred. Please try again.
          </p>
          {error.digest && (
            <p className="text-xs text-white/30 mb-4">
              Error ID: {error.digest}
            </p>
          )}
          <button
            onClick={reset}
            className="px-4 py-2 rounded-md bg-accent text-white text-sm font-medium hover:bg-accent/90 transition-colors"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}