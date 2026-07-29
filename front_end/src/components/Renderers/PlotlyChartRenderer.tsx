"use client";

import { useState } from "react";
import { Loader2, Maximize2, Minimize2 } from "lucide-react";
import dynamic from "next/dynamic";

import type { PlotlySpec } from "@/lib/types";

// react-plotly.js uses `window` and must be loaded only on the client.
const Plot = dynamic(
  () => import("react-plotly.js").then((m) => m.default as never),
  { ssr: false }
) as unknown as React.ComponentType<Record<string, unknown>>;

interface PlotlyChartRendererProps {
  /** The raw Plotly figure dict ({data, layout}) from backend's plotly_specs. */
  spec: PlotlySpec;
  title?: string;
  height?: number;
  className?: string;
}

/**
 * Renders a Plotly chart from a JSON spec ({data: [...], layout: {...}}).
 * 
 * Backend returns this directly in `plotly_specs` — the raw figure dict
 * serialized from Python's fig.to_json() / fig.to_dict().
 */
export function PlotlyChartRenderer({
  spec,
  title,
  height = 480,
  className = "",
}: PlotlyChartRendererProps) {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(true);

  // Backend sends the raw figure dict directly (not wrapped in {figure:...})
  const data = Array.isArray(spec?.data)
    ? (spec.data as unknown[])
    : [];
  const layout = (spec?.layout as Record<string, unknown>) || {};

  return (
    <div
      className={`rounded-lg border border-white/10 bg-bg/50 overflow-hidden transition-all duration-300 ${
        expanded ? "fixed inset-4 z-50" : ""
      } ${className}`}
    >
      {/* Header bar */}
      <div className="flex items-center justify-between gap-2 px-3 py-2 bg-white/5 border-b border-white/5">
        <div className="flex items-center gap-2 text-xs text-white/70 truncate">
          <span className="font-medium truncate">{title ?? "Interactive chart"}</span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1 rounded hover:bg-white/10 text-white/50 hover:text-white/80 transition-colors"
            title={expanded ? "Minimize" : "Expand"}
          >
            {expanded ? (
              <Minimize2 className="h-3.5 w-3.5" />
            ) : (
              <Maximize2 className="h-3.5 w-3.5" />
            )}
          </button>
        </div>
      </div>

      {/* Loading overlay */}
      {loading && (
        <div className="flex items-center justify-center py-12 text-white/40 gap-2">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="text-sm">Loading chart...</span>
        </div>
      )}

      {/* Plotly chart */}
      <div
        className={`w-full transition-opacity duration-300 ${
          loading ? "h-0 opacity-0" : expanded ? "h-[calc(100vh-8rem)]" : ""
        }`}
        style={loading ? undefined : { height: expanded ? undefined : height }}
      >
        <Plot
          data={data}
          layout={{ ...layout, autosize: true }}
          config={{ responsive: true, displaylogo: false }}
          style={{ width: "100%", height: "100%" }}
          onInitialized={() => setLoading(false)}
          useResizeHandler
        />
      </div>
    </div>
  );
}
