"use client";

import { useMemo, useState } from "react";
import { BarChart3, ChevronLeft, ChevronRight, Image, Code } from "lucide-react";

import { ChartRenderer } from "@/components/analytics/ChartRenderer";
import { PlotlyHtmlRenderer } from "@/components/Renderers/PlotlyHtmlRenderer";
import type { AiChartSpec } from "@/lib/types";
import { classNames } from "@/utils/format";

interface VisualizationViewerProps {
  /** Chart.js specs from the chat backend */
  charts?: AiChartSpec[];
  /** Sandbox files from execute_python_code */
  sandboxFiles?: string[];
  /** Optional className */
  className?: string;
}

type TabType = "chartjs" | "html" | "png";

/**
 * VisualizationViewer — groups multiple visualizations into a
 * tabbed carousel interface.
 *
 * - "Chart.js" tab: lists all ChartRenderer charts
 * - "Interactive" tab: lists Plotly HTML files
 * - "Images" tab: lists PNG files
 *
 * Each tab supports prev/next navigation when multiple items exist.
 */
export function VisualizationViewer({
  charts = [],
  sandboxFiles = [],
  className = "",
}: VisualizationViewerProps) {
  const [activeTab, setActiveTab] = useState<TabType>("chartjs");
  const [activeIndex, setActiveIndex] = useState(0);

  const htmlFiles = useMemo(
    () => sandboxFiles.filter((f) => f.endsWith(".html")),
    [sandboxFiles]
  );
  const pngFiles = useMemo(
    () => sandboxFiles.filter((f) => f.endsWith(".png")),
    [sandboxFiles]
  );

  const hasCharts = charts.length > 0;
  const hasHtml = htmlFiles.length > 0;
  const hasPng = pngFiles.length > 0;

  // Auto-switch tab if active tab has no items but others do
  const resolvedTab: TabType = useMemo(() => {
    if (activeTab === "chartjs" && !hasCharts && (hasHtml || hasPng)) {
      return hasHtml ? "html" : "png";
    }
    if (activeTab === "html" && !hasHtml && (hasCharts || hasPng)) {
      return hasCharts ? "chartjs" : "png";
    }
    if (activeTab === "png" && !hasPng && (hasCharts || hasHtml)) {
      return hasCharts ? "chartjs" : "html";
    }
    return activeTab;
  }, [activeTab, hasCharts, hasHtml, hasPng]);

  const totalItems =
    resolvedTab === "chartjs"
      ? charts.length
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
  if (!hasCharts && !hasHtml && !hasPng) {
    return null;
  }

  return (
    <div className={classNames("my-3 rounded-lg border border-white/5 bg-bg/40 overflow-hidden", className)}>
      {/* Tabs */}
      <div className="flex border-b border-white/5">
        {hasCharts && (
          <TabButton
            active={resolvedTab === "chartjs"}
            onClick={() => {
              setActiveTab("chartjs");
              setActiveIndex(0);
            }}
            icon={<BarChart3 className="h-3.5 w-3.5" />}
            label={`Charts (${charts.length})`}
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
            label={`Interactive (${htmlFiles.length})`}
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
          {resolvedTab === "chartjs" && hasCharts && (
            <div>
              <div className="mb-1 text-xs text-white/50 text-center">
                {charts[safeIndex]?.chart_title || `Chart ${safeIndex + 1}`}
                {hasMultiple && (
                  <span className="ml-2 text-white/30">
                    ({safeIndex + 1}/{totalItems})
                  </span>
                )}
              </div>
              <ChartRenderer spec={charts[safeIndex]} height={280} />
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
      {label}
    </button>
  );
}