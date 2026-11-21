import { HeatmapChart as HeatmapSeries } from "echarts/charts";
import { GridComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { afterEach, describe, expect, it } from "vitest";
import type { Tokens } from "./charts/EChart";
import { heatmapOption, type Cell } from "./HeatmapChart";

echarts.use([SVGRenderer, GridComponent, TooltipComponent, VisualMapComponent, HeatmapSeries]);

// Cores distintas por token: o SVG renderizado mostra qual célula pegou qual cor.
const T: Tokens = {
  surface: "#fefefe",
  sunken: "#eeeeee",
  rule: "#a1b2c3",
  ink: "#111111",
  muted: "#777777",
  crit: "#cc0000",
  warn: "#cc8800",
  good: "#008800",
  series: "#880044",
  seriesDeep: "#440022",
  seriesSoft: "#ddaacc",
};

function cell(hour: number, weekday: number, sla: number, lowSample: boolean): Cell {
  return {
    weekday,
    hour,
    orders: lowSample ? 5 : 80,
    measured: lowSample ? 4 : 70,
    sla_rate: sla,
    cancel_rate: 0.02,
    cycle_p50: 40,
    low_sample: lowSample,
    volume_low_sample: lowSample,
  } as Cell;
}

const FIRM = [cell(10, 0, 0.8, false), cell(12, 1, 0.95, false)];
const THIN = [cell(3, 2, 0.5, true)];

let chart: echarts.ECharts | null = null;
afterEach(() => {
  chart?.dispose();
  chart = null;
});

function render(option: ReturnType<typeof heatmapOption>): string {
  chart = echarts.init(null, null, { renderer: "svg", ssr: true, width: 600, height: 300 });
  chart.setOption({ ...option, animation: false });
  return chart.renderToSVGString();
}

describe("heatmapOption", () => {
  // Em dev o ECharts lança "Heatmap must use with visualMap" para série heatmap sem visualMap.
  it("usa uma só série heatmap, coberta pelo visualMap", () => {
    const option = heatmapOption(T, { firm: FIRM, thin: THIN, metric: "sla_rate", peak: new Set() });
    expect(option.series).toHaveLength(1);
    expect(option.series[0].type).toBe("heatmap");
    expect(option.visualMap.seriesIndex).toBe(0);
  });

  it.each([
    ["com células de amostra pequena", THIN, new Set<number>()],
    ["sem células de amostra pequena", [], new Set<number>()],
    ["com horas da comanda em destaque", THIN, new Set([3, 10])],
  ])("renderiza sem erro %s", (_label, thin, peak) => {
    expect(() => render(heatmapOption(T, { firm: FIRM, thin, metric: "sla_rate", peak }))).not.toThrow();
  });

  it("pinta a célula de amostra pequena de cinza, fora da escala", () => {
    const svg = render(heatmapOption(T, { firm: FIRM, thin: THIN, metric: "sla_rate", peak: new Set() }));
    expect(svg.match(new RegExp(`fill="${T.rule}"`, "g"))).toHaveLength(1);
    // a escala sai só das firmes: a cinza (50%) não vira o mínimo
    const option = heatmapOption(T, { firm: FIRM, thin: THIN, metric: "sla_rate", peak: new Set() });
    expect(option.visualMap.min).toBe(0.8);
    expect(option.visualMap.max).toBe(0.95);
  });

  it("marca a célula cinza no tooltip e escapa o texto", () => {
    const option = heatmapOption(T, { firm: FIRM, thin: THIN, metric: "sla_rate", peak: new Set() });
    const data = option.series[0].data as { value: readonly number[] }[];
    const thinItem = data.find((d) => typeof d === "object" && "value" in d && d.value[5] === 1);
    expect(thinItem).toBeDefined();
    const html = option.tooltip.formatter({ value: [...thinItem!.value] });
    expect(html).toContain("Amostra pequena (fora da escala)");
    const firmHtml = option.tooltip.formatter({ value: [10, 0, 0.8, 80, 70, 0] });
    expect(firmHtml).not.toContain("Amostra pequena");
  });
});
