// Type stubs for the `react-plotly.js` module. The upstream package does
// not ship its own types, so we expose just enough surface area to
// satisfy the renderer in this project. Add more fields here if you
// need a stricter type.

declare module "react-plotly.js" {
  import type { ComponentType, CSSProperties } from "react";

  export interface PlotParams {
    data: unknown[];
    layout?: Record<string, unknown> | object;
    config?: Record<string, unknown> | object;
    style?: CSSProperties;
    className?: string;
    useResizeHandler?: boolean;
    onInitialized?: (figure: unknown, graphDiv: unknown) => void;
    onUpdate?: (figure: unknown, graphDiv: unknown) => void;
    onPurge?: (figure: unknown, graphDiv: unknown) => void;
    onClick?: (data: unknown) => void;
    onBeforePlot?: (figure: unknown) => void;
    onAfterPlot?: (figure: unknown) => void;
    onError?: (err: unknown) => void;
    onLegendClick?: (event: unknown) => void;
    onLegendDoubleClick?: (event: unknown) => void;
    onSelected?: (event: unknown) => void;
    onSelecting?: (event: unknown) => void;
  }

  const Plot: ComponentType<PlotParams>;
  export default Plot;
}
