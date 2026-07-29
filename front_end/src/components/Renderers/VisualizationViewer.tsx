"use client";

import { useMemo, useState } from "react";
import { BarChart3, ChevronLeft, ChevronRight, Image, Code } from "lucide-react";

import { ChartRenderer } from "@/components/analytics/ChartRenderer";
import { PlotlyChartRenderer } from "@/components/Renderers/PlotlyChartRenderer";
import { PlotlyHtmlRenderer } from "@/components/Renderers/PlotlyHtmlRenderer";
import type { AiChartSpec, PlotlySpec } from "@/lib/types";
import { classNames } from "@/utils/format";

interface VisualizationViewerProps {
  /** Chart.js specs from the chat backend */
  charts?: AiChartSpec[];
  /**
   * Plotly figures as JSON specs (returned by the E2B sandbox as
   * fig.to_dict()). Rendered directly via react-plotly.js, no iframe
   * involved.
   */
  plotlySpecs?: PlotlySpec[];
  /** Optional title for the most-recent Plotly figure. */
  plotlyTitle?: string;
  /** Sandbox files from execute_python_code (legacy iframe HTML, PNG, etc.) */
  sandboxFiles?: string[];
  /** Optional className */
  className?: string;
}

type TabType = "plotly" | "html" | "png";

/**
 * VisualizationViewer — groups multiple visualizations into a
 * tabbed carousel interface.
 *
 * - "Interactive" tab: Plotly figures rendered via react-plotly.js
 *   (preferred — no iframe, no CSP / X-Frame-Options issues).
 * - "Chart.js" tab: lists all ChartRenderer charts.
 * - "HTML" tab: legacy Plotly HTML files served via /api/v1/data-files.
 * - "Images" tab: PNG files.
 */
export function VisualizationViewer({
  charts = [],
  plotlySpecs = [],
  plotlyTitle,
  sandboxFiles = [],
  className = "",
}: VisualizationViewerProps) {
  const [activeTab, setActiveTab] = useState<TabType>("plotly");
  const [activeIndex, setActiveIndex] = useState(0);

  const htmlFiles = useMemo(
    () => sandboxFiles.filter((f) => f.endsWith(".html")),
    [sandboxFiles]
  );
  const pngFiles = useMemo(
    () => sandboxFiles.filter((f) => f.endsWith(".png")),
    [sandboxFiles]
  );

  const hasPlotly = plotlySpecs.length > 0;
  const hasCharts = charts.length > 0;
  const hasHtml = htmlFiles.length > 0;
  const hasPng = pngFiles.length > 0;

  // Auto-switch tab if active tab has no items but others do
  const resolvedTab: TabType = useMemo(() => {
    const ordered: TabType[] = ["plotly", "html", "png"];
    if (ordered.includes(activeTab)) {
      const hasCurrent =
        (activeTab === "plotly" && hasPlotly) ||
        (activeTab === "html" && hasHtml) ||
        (activeTab === "png" && hasPng);
      if (hasCurrent) return activeTab;
    }
    // Pick the first tab that has items
    for (const t of ordered) {
      if (
        (t === "plotly" && hasPlotly) ||
        (t === "html" && hasHtml) ||
        (t === "png" && hasPng)
      ) {
        return t;
      }
    }
    return activeTab;
  }, [activeTab, hasPlotly, hasCharts, hasHtml, hasPng]);

  const totalItems =
    resolvedTab === "plotly"
      ? plotlySpecs.length
      : resolvedTab === "html"
      ? htmlFiles.length
      : pngFiles.length;

  const safeIndex = Math.min(activeIndex, Math.max(0, totalItems - 1));
  const hasMultiple = totalItems > 1;

  const handlePrev = () => {
    setActiveIndex((i) => (i <= 0 ? totalItems - 1 : i - 1));
  };
  const handleNext = () => {
    setActiveIndex((i) => (i >= totalItems - 1 ? 0 : i + 1));
  };

  // Nothing to show
  if (!hasPlotly && !hasCharts && !hasHtml && !hasPng) {
    return null;
  }

  return (
    <div className={classNames("my-3 rounded-lg border border-white/5 bg-bg/40 overflow-hidden", className)}>
      {/* Tabs */}
      <div className="flex border-b border-white/5">
        {hasPlotly && (
          <TabButton
            active={resolvedTab === "plotly"}
            onClick={() => {
              setActiveTab("plotly");
              setActiveIndex(0);
            }}
            icon={<BarChart3 className="h-3.5 w-3.5" />}
            label={`Charts (${plotlySpecs.length})`}
          />
        )}
        {hasHtml && (
          <TabButton
            active={resolvedTab === "html"}
            onClick={() => {
              setActiveTab("html");
              setActiveIndex(0);
            }}
            icon={<Code className="h-3.5 w-3.5" />}
            label={`Legacy HTML (${htmlFiles.length})`}
          />
        )}
        {hasPng && (
          <TabButton
            active={resolvedTab === "png"}
            onClick={() => {
              setActiveTab("png");
              setActiveIndex(0);
            }}
            icon={<Image className="h-3.5 w-3.5" />}
            label={`Images (${pngFiles.length})`}
          />
        )}
      </div>

      {/* Content area */}
      <div className="relative">
        {/* Navigation arrows */}
        {hasMultiple && (
          <>
            <button
              onClick={handlePrev}
              className="absolute left-0 top-1/2 z-10 -translate-y-1/2 rounded-r-md bg-black/30 p-1 text-white/70 hover:bg-black/50 hover:text-white transition-colors"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
            <button
              onClick={handleNext}
              className="absolute right-0 top-1/2 z-10 -translate-y-1/2 rounded-l-md bg-black/30 p-1 text-white/70 hover:bg-black/50 hover:text-white transition-colors"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
          </>
        )}

        {/* Tab content */}
        <div className="p-2">
          {resolvedTab === "plotly" && hasPlotly && (
            <div>
              <div className="mb-1 text-xs text-white/50 text-center">
                {plotlyTitle ??
                  (() => {
                    const spec = plotlySpecs[safeIndex];
                    const layout = spec?.layout as Record<string, unknown> | undefined;
                    const lt = layout?.title;
                    if (typeof lt === "string") return lt;
                    if (typeof lt === "object" && lt !== null && "text" in lt) {
                      return (lt as Record<string, unknown>).text as string;
                    }
                    return null;
                  })() ??
                  `Interactive (${safeIndex + 1}/${totalItems})`}
                {hasMultiple && (
                  <span className="ml-2 text-white/30">
                    ({safeIndex + 1}/{totalItems})
                  </span>
                )}
              </div>
              <PlotlyChartRenderer
                spec={plotlySpecs[safeIndex]}
                title={plotlyTitle}
                height={320}
              />
            </div>
          )}

          {resolvedTab === "html" && hasHtml && (
            <PlotlyHtmlRenderer
              filename={htmlFiles[safeIndex]}
              title={`Interactive (${safeIndex + 1}/${totalItems})`}
            />
          )}

          {resolvedTab === "png" && hasPng && (
            <div className="text-center">
              <div className="mb-1 text-xs text-white/50">
                {pngFiles[safeIndex]}
                {hasMultiple && (
                  <span className="ml-2 text-white/30">
                    ({safeIndex + 1}/{totalItems})
                  </span>
                )}
              </div>
              <img
                src={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}/temp_data/${pngFiles[safeIndex]}`}
                alt={pngFiles[safeIndex]}
                className="mx-auto max-h-[500px] w-auto rounded"
              />
            </div>
          )}
        </div>
      </div>

      {/* Dots indicator for multiple items */}
      {hasMultiple && (
        <div className="flex items-center justify-center gap-1.5 pb-2">
          {Array.from({ length: totalItems }, (_, i) => (
            <button
              key={i}
              onClick={() => setActiveIndex(i)}
              className={classNames(
                "h-1.5 w-1.5 rounded-full transition-all duration-200",
                i === safeIndex
                  ? "bg-accent w-3"
                  : "bg-white/20 hover:bg-white/40"
              )}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={classNames(
        "flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors",
        active
          ? "border-b-2 border-accent text-accent bg-white/5"
          : "text-white/50 hover:text-white/70 hover:bg-white/[0.02]"
      )}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}
