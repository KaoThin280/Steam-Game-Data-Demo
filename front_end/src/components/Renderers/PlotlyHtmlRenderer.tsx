"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Maximize2, Minimize2, ExternalLink } from "lucide-react";

interface PlotlyHtmlRendererProps {
  /** Filename in temp_data/ (e.g. "chart.html") */
  filename: string;
  /** Title to show above the iframe */
  title?: string;
  /** If true, expand to full viewport height on click */
  expandable?: boolean;
  /** Optional className */
  className?: string;
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/**
 * Renders a Plotly interactive HTML chart inside a sandboxed iframe.
 *
 * The backend serves Plotly HTML files inline via GET /api/v1/data-files/{filename}.
 * The iframe is sandboxed so Plotly's JS can run but the parent page is isolated.
 */
export function PlotlyHtmlRenderer({
  filename,
  title,
  expandable = true,
  className = "",
}: PlotlyHtmlRendererProps) {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const fileUrl = `${API_BASE}/data-files/${filename}`;

  const handleLoad = useCallback(() => {
    setLoading(false);
  }, []);

  const handleError = useCallback(() => {
    setLoading(false);
    setError(`Failed to load: ${filename}`);
  }, [filename]);

  // Reset loading state when filename changes
  useEffect(() => {
    setLoading(true);
    setError(null);
  }, [filename]);

  const displayTitle = title || filename;

  return (
    <div
      className={`rounded-lg border border-white/10 bg-bg/50 overflow-hidden transition-all duration-300 ${
        expanded ? "fixed inset-4 z-50" : ""
      } ${className}`}
    >
      {/* Header bar */}
      <div className="flex items-center justify-between gap-2 px-3 py-2 bg-white/5 border-b border-white/5">
        <div className="flex items-center gap-2 text-xs text-white/70 truncate">
          <span className="font-medium truncate">{displayTitle}</span>
          <span className="text-white/40 hidden sm:inline">{filename}</span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <a
            href={fileUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1 rounded hover:bg-white/10 text-white/50 hover:text-white/80 transition-colors"
            title="Open in new tab"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
          {expandable && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="p-1 rounded hover:bg-white/10 text-white/50 hover:text-white/80 transition-colors"
              title={expanded ? "Minimize" : "Expand"}
            >
              {expanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
            </button>
          )}
        </div>
      </div>

      {/* Loading overlay */}
      {loading && (
        <div className="flex items-center justify-center py-12 text-white/40 gap-2">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="text-sm">Loading chart...</span>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="flex items-center justify-center py-12 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Iframe - hidden while loading */}
      <iframe
        ref={iframeRef}
        src={fileUrl}
        title={displayTitle}
        className={`w-full border-0 transition-opacity duration-300 ${
          loading ? "h-0 opacity-0" : expanded ? "h-[calc(100vh-8rem)]" : "h-[500px]"
        }`}
        sandbox="allow-scripts allow-same-origin"
        onLoad={handleLoad}
        onError={handleError}
        style={{ opacity: loading ? 0 : 1 }}
      />
    </div>
  );
}