"use client";

import { useEffect, useMemo, useRef } from "react";
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  type ChartConfiguration,
  type ChartData,
  type ChartOptions,
  type ChartType,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  RadialLinearScale,
  Title,
  Tooltip,
} from "chart.js";
import { Chart } from "react-chartjs-2";

import type { AiChartSpec } from "@/lib/types";

ChartJS.register(
  ArcElement,
  BarElement,
  CategoryScale,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  RadialLinearScale,
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

  const ctype = (spec.chart_type || "bar").toLowerCase();
  const resolvedType: ChartType = ctype === "area" ? "line" : (ctype as ChartType);

  const data: ChartData = useMemo(
    () => ({
      labels: spec.config.labels,
      datasets: spec.config.datasets.map((d) => ({
        ...d,
        fill: ctype === "area" ? true : d.fill,
      })),
    }),
    [spec.config, ctype]
  );

  const options: ChartOptions = useMemo(() => {
    const isLinear = resolvedType === "bar" || resolvedType === "line"
      || resolvedType === "scatter";
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: "bottom" as const },
        title: { display: false },
      },
      scales: isLinear
        ? {
            x: {
              title: spec.x_axis_label
                ? { display: true, text: spec.x_axis_label }
                : undefined,
              ticks: { autoSkip: true, maxRotation: 45, minRotation: 0 },
            },
            y: {
              title: spec.y_axis_label
                ? { display: true, text: spec.y_axis_label }
                : undefined,
              beginAtZero: true,
            },
          }
        : undefined,
    };
  }, [resolvedType, spec.x_axis_label, spec.y_axis_label]);

  const cfg: ChartConfiguration = {
    type: resolvedType,
    data,
    options,
  };

  useEffect(() => () => chartRef.current?.destroy(), []);

  return (
    <div style={{ height }} className="w-full">
      <Chart ref={chartRef} {...cfg} />
      {spec.notes && (
        <p className="mt-2 text-xs text-white/60">{spec.notes}</p>
      )}
    </div>
  );
}
