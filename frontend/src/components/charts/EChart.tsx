/**
 * Wrapper fino do ECharts (tree-shaken, renderer Canvas). Recria o tema quando
 * o átomo $theme muda e redimensiona via ResizeObserver.
 */
import { useStore } from "@nanostores/react";
import { BarChart, HeatmapChart, LineChart, ScatterChart } from "echarts/charts";
import {
  BrushComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  ToolboxComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useMemo, useRef } from "react";
import { $theme, tokens } from "@/lib/theme";

echarts.use([
  BarChart,
  LineChart,
  HeatmapChart,
  ScatterChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  VisualMapComponent,
  BrushComponent,
  ToolboxComponent,
  MarkLineComponent,
  CanvasRenderer,
]);

export type Tokens = ReturnType<typeof tokens>;
export type ECOption = echarts.EChartsCoreOption;
export type ECInstance = echarts.ECharts;

type Handler = (params: any, chart: ECInstance) => void;

interface Props {
  /** Recebe os tokens resolvidos do tema para montar a opção. */
  option: (t: Tokens) => ECOption;
  height?: number;
  onEvents?: Record<string, Handler>;
  onReady?: (chart: ECInstance) => void;
  ariaLabel: string;
}

function baseTheme(t: Tokens) {
  return {
    color: [t.chili, t.muted, t.amber, t.chiliDeep, t.ink],
    backgroundColor: "transparent",
    textStyle: { color: t.ink, fontFamily: "Source Sans 3, ui-sans-serif, system-ui, sans-serif", fontSize: 12 },
    tooltip: {
      backgroundColor: t.paper,
      borderColor: t.rule,
      textStyle: { color: t.ink, fontSize: 12 },
      extraCssText: "box-shadow:none;border-radius:6px;",
    },
    legend: { textStyle: { color: t.muted } },
    categoryAxis: {
      axisLine: { lineStyle: { color: t.rule } },
      axisTick: { show: false },
      axisLabel: { color: t.muted },
      splitLine: { show: false },
    },
    valueAxis: {
      axisLine: { show: false },
      axisLabel: { color: t.muted },
      splitLine: { lineStyle: { color: t.rule } },
    },
    timeAxis: {
      axisLine: { lineStyle: { color: t.rule } },
      axisLabel: { color: t.muted },
      splitLine: { show: false },
    },
  };
}

export function EChart({ option, height = 320, onEvents, onReady, ariaLabel }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ECInstance | null>(null);
  const theme = useStore($theme);
  const handlers = useRef(onEvents);
  handlers.current = onEvents;

  // (re)cria a instância quando o tema muda: o tema ECharts é fixado na criação
  useEffect(() => {
    if (!ref.current) return;
    const t = tokens();
    const name = `ops-${theme}`;
    echarts.registerTheme(name, baseTheme(t));
    const chart = echarts.init(ref.current, name, { renderer: "canvas" });
    chartRef.current = chart;
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current);
    const events = Object.keys(handlers.current ?? {});
    events.forEach((evt) => chart.on(evt, (p: unknown) => handlers.current?.[evt]?.(p, chart)));
    onReady?.(chart);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme]);

  const built = useMemo(() => (typeof window === "undefined" ? null : option(tokens())), [option, theme]);

  useEffect(() => {
    if (chartRef.current && built) chartRef.current.setOption(built, { notMerge: true, lazyUpdate: true });
  }, [built]);

  return <div ref={ref} role="img" aria-label={ariaLabel} style={{ height, width: "100%" }} />;
}
