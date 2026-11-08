/**
 * Wrapper fino do ECharts (tree-shaken, renderer Canvas).
 *
 * A instância nasce uma vez e só é descartada no desmonte: trocar o recorte ou
 * o tema não a recria, então o gráfico não pisca. Dados novos entram por
 * setOption com notMerge; séries com id estável deixam o ECharts reaproveitar
 * as views e animar a transição. Trocar o tema usa setTheme, sem animação, e
 * reaplica a opção com as cores novas. prefers-reduced-motion desliga a
 * animação em todo setOption.
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
import { $theme, tokens, type Theme } from "@/lib/theme";

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

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

/** Duração e easing de todo gráfico: entrada e atualização com o mesmo ritmo. */
const MOTION_DEFAULTS = {
  animationDuration: 300,
  animationDurationUpdate: 300,
  animationEasingUpdate: "cubicOut",
} as const;

/** O tema ECharts é fixado por nome; um nome por tema evita reler um tema antigo. */
const themeName = (theme: Theme) => `ops-${theme}`;

/**
 * Aplica a flag `animation` e as durações em cada setOption, no nível global e
 * em cada série. As séries têm default próprio de `animation`, então o global
 * sozinho não desliga a animação delas (a linha anima `points` por conta própria).
 */
function withMotion(option: ECOption, animate: boolean): ECOption {
  const series = (option as { series?: unknown }).series;
  const motionSeries = (s: unknown) => ({ ...MOTION_DEFAULTS, ...(s as object), animation: animate });
  return {
    ...MOTION_DEFAULTS,
    ...option,
    animation: animate,
    ...(Array.isArray(series) ? { series: series.map(motionSeries) } : {}),
  };
}

type Range = { start?: number; end?: number }[];

/** Faixa atual (em %) de cada dataZoom do gráfico. */
function readRange(chart: ECInstance): Range {
  return ((chart.getOption().dataZoom ?? []) as Range).map((z) => ({ start: z.start, end: z.end }));
}

/**
 * setTheme redefine o dataZoom para o padrão (0 a 100). Depois da troca, a
 * faixa lida antes volta à opção, então o zoom do usuário sobrevive ao tema.
 */
function withRange(option: ECOption, range: Range): ECOption {
  const next = (option as { dataZoom?: unknown }).dataZoom;
  if (!Array.isArray(next)) return option;
  return {
    ...option,
    dataZoom: next.map((z, i) =>
      range[i]?.start != null && range[i]?.end != null ? { ...z, start: range[i].start, end: range[i].end } : z,
    ),
  };
}

/**
 * Troca o tema sem transição: a opção sem animação vai antes e depois do
 * setTheme (que redefine o dataZoom), e as transições que ainda restarem vão
 * direto ao estado final. Tudo síncrono, para nada ser desenhado no meio.
 */
function swapTheme(chart: ECInstance, name: string, option: ECOption) {
  chart.setOption(option);
  chart.setTheme(name);
  chart.setOption(option);
  // API interna do zrender: se mudar numa versão futura, a troca só deixa de ser instantânea.
  try {
    chart.getZr().storage.traverse((el) => {
      el.stopAnimation(undefined, true);
    });
  } catch {
    /* sem efeito visual além de uma transição curta */
  }
}

function baseTheme(t: Tokens) {
  return {
    color: [t.series, t.ink, t.muted, t.seriesDeep, t.warn],
    backgroundColor: "transparent",
    textStyle: { color: t.ink, fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif", fontSize: 12 },
    tooltip: {
      backgroundColor: t.surface,
      borderColor: t.rule,
      textStyle: { color: t.ink, fontSize: 12 },
      extraCssText: "box-shadow:none;border-radius:8px;",
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
  // Tema aplicado na instância. Se difere do átomo, a próxima atualização troca o tema.
  const appliedTheme = useRef<Theme>(theme);
  // Preferência de movimento reduzido; o listener do media query mantém o valor atual.
  const reducedMotion = useRef(false);
  const handlers = useRef(onEvents);
  handlers.current = onEvents;
  const readyRef = useRef(onReady);
  readyRef.current = onReady;

  // Cria a instância uma única vez e a descarta só no desmonte.
  useEffect(() => {
    if (!ref.current) return;
    echarts.registerTheme(themeName(appliedTheme.current), baseTheme(tokens()));
    const chart = echarts.init(ref.current, themeName(appliedTheme.current), { renderer: "canvas" });
    chartRef.current = chart;
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current);
    Object.keys(handlers.current ?? {}).forEach((evt) => chart.on(evt, (p: unknown) => handlers.current?.[evt]?.(p, chart)));
    readyRef.current?.(chart);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  // Acompanha a preferência de movimento reduzido, inclusive quando muda com a página aberta.
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const query = window.matchMedia(REDUCED_MOTION_QUERY);
    reducedMotion.current = query.matches;
    const onChange = (e: MediaQueryListEvent) => {
      reducedMotion.current = e.matches;
    };
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  const built = useMemo(() => (typeof window === "undefined" ? null : option(tokens())), [option, theme]);

  // Aplica tema e dados. Troca de tema: swapTheme, sem animação, mantendo o zoom.
  // Dados: notMerge, com séries de id estável; o ECharts reaproveita as views e anima a transição.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !built) return;
    if (appliedTheme.current !== theme) {
      // Troca só o tema: a faixa do zoom é lida antes e devolvida, pois setTheme a redefine.
      appliedTheme.current = theme;
      const next = withRange(built, readRange(chart));
      echarts.registerTheme(themeName(theme), baseTheme(tokens()));
      swapTheme(chart, themeName(theme), withMotion(next, false));
      return;
    }
    chart.setOption(withMotion(built, !reducedMotion.current), { notMerge: true, lazyUpdate: true });
  }, [built, theme]);

  return <div ref={ref} role="img" aria-label={ariaLabel} style={{ height, width: "100%" }} />;
}
