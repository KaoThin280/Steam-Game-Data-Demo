"use client";

import { useEffect, useMemo, useRef } from "react";
import {
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  type ChartConfiguration,
  type ChartData,
  type ChartOptions,
  type ChartType,
  DoughnutController,
  Filler,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PieController,
  PointElement,
  PolarAreaController,
  RadarController,
  RadialLinearScale,
  ScatterController,
  Title,
  Tooltip,
} from "chart.js";
import { Chart } from "react-chartjs-2";

import type { AiChartSpec } from "@/lib/types";
import { useTheme } from "@/components/layout/ThemeProvider";

ChartJS.register(
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  DoughnutController,
  Filler,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PieController,
  PointElement,
  PolarAreaController,
  RadarController,
  RadialLinearScale,
  ScatterController,
  Title,
  Tooltip
);

interface ChartRendererProps {
  spec: AiChartSpec;
  height?: number;
}

/**
 * Render a Chart.js configuration coming from the AI `charting` tool.
 *
 * Accepts:
 *   chart_type: bar | line | pie | doughnut | scatter | radar | polarArea
 *   config: { labels, datasets }
 *
 * Optional fields (x_axis_label / y_axis_label / y_unit / x_rotation)
 * are honoured. `area` is auto-converted to a filled line chart
 * (Chart.js needs the same elements + fill: true on the dataset).
 */
export function ChartRenderer({ spec, height = 320 }: ChartRendererProps) {
  const chartRef = useRef<ChartJS | null>(null);
  const { theme } = useTheme();

  const ctype = (spec.chart_type || "bar").toLowerCase();
  const resolvedType: ChartType = ctype === "area" ? "line" : (ctype as ChartType);

  // Merge AI-provided config with defaults — AI colors/options take precedence
  const data: ChartData = useMemo(() => {
    const palette = ["#2563eb", "#0891b2", "#7c3aed", "#db2777", "#ea580c", "#16a34a", "#ca8a04", "#4f46e5", "#0f766e", "#dc2626"];
    const circular = ["pie", "doughnut", "polarArea"].includes(resolvedType);
    return ({
      labels: spec.config.labels,
      datasets: spec.config.datasets.map((d, index) => ({
        ...d,
        fill: ctype === "area" ? true : d.fill,
        borderColor: d.borderColor ?? (circular ? "#ffffff" : palette[index % palette.length]),
        backgroundColor: d.backgroundColor ?? (circular ? palette : `${palette[index % palette.length]}cc`),
        pointBackgroundColor: d.pointBackgroundColor ?? palette[index % palette.length],
        pointRadius: d.pointRadius ?? (resolvedType === "line" ? 2 : undefined),
        borderWidth: d.borderWidth ?? 2,
      })),
    });
  }, [spec.config, ctype, resolvedType]);

  // Use AI-provided options if present, otherwise fall back to defaults
  const options: ChartOptions = useMemo(() => {
    const aiOptions = spec.config.options || {};
    const isLinear = resolvedType === "bar" || resolvedType === "line"
      || resolvedType === "scatter";
    const foreground = theme === "dark" ? "#e2e8f0" : "#334155";
    const muted = theme === "dark" ? "#94a3b8" : "#64748b";
    const grid = theme === "dark" ? "rgba(148,163,184,.14)" : "rgba(100,116,139,.16)";
    return {
      responsive: true,
      maintainAspectRatio: false,
      ...aiOptions,
      plugins: {
        legend: { display: true, position: "bottom" as const, labels: { color: foreground, usePointStyle: true, padding: 18 } },
        title: { display: false },
        tooltip: { enabled: true, backgroundColor: theme === "dark" ? "#0f172a" : "#ffffff", titleColor: foreground, bodyColor: foreground, borderColor: theme === "dark" ? "#334155" : "#e2e8f0", borderWidth: 1 },
        ...(aiOptions.plugins || {}),
      },
      scales: isLinear
        ? {
            x: {
              grid: { color: grid },
              title: spec.x_axis_label
                ? { display: true, text: spec.x_axis_label }
                : undefined,
              ticks: { autoSkip: true, maxRotation: 45, minRotation: 0, color: muted },
              ...((aiOptions.scales as Record<string, unknown>)?.["x"] as Record<string, unknown> || {}),
            },
            y: {
              grid: { color: grid },
              title: spec.y_axis_label
                ? { display: true, text: spec.y_axis_label }
                : undefined,
              beginAtZero: true,
              ticks: { color: muted },
              ...((aiOptions.scales as Record<string, unknown>)?.["y"] as Record<string, unknown> || {}),
            },
          }
        : aiOptions.scales || undefined,
    };
  }, [resolvedType, spec.x_axis_label, spec.y_axis_label, spec.config.options, theme]);

  const cfg: ChartConfiguration = {
    type: resolvedType,
    data,
    options,
  };

  useEffect(() => {
    return () => {
      const chart = chartRef.current;
      if (chart && typeof chart.destroy === "function") {
        chart.destroy();
      }
    };
  }, []);

  return (
    <div style={{ height }} className="w-full">
      <Chart ref={chartRef} {...cfg} />
      {spec.notes && (
        <p className="mt-2 text-xs text-muted">{spec.notes}</p>
      )}
    </div>
  );
}
