import { useStore } from "@nanostores/react";
import { CalendarCheck, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { $filters, $view, patchFilters, setView, type TrendGrain, type TrendView } from "@/lib/filters";
import { fmt } from "@/lib/format";
import { island, useRecorteQuery } from "@/lib/query";
import { BarChart, LineChart } from "echarts/charts";
import { DataZoomComponent, LegendComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { ChartAccess } from "./charts/ChartAccess";
import { EChart, type ECInstance, type Tokens } from "./charts/EChart";
import { AskAgentButton } from "./ui/AskAgentButton";
import { AsyncBody, Empty, panelFallback, PanelContent, Segmented } from "./ui/Panel";

// Módulos deste gráfico: barras, linhas, zoom (interno e barra) e legenda. O resto fica em charts/EChart.tsx.
echarts.use([BarChart, LineChart, DataZoomComponent, LegendComponent]);

/** Altura do gráfico e do skeleton: a mesma nos três estados, para o layout não pular. */
const CHART_H = 340;

const GRAIN_LABEL: Record<TrendGrain, string> = { hour: "Hora", day: "Dia", week: "Semana" };
const VIEW_LABEL: Record<TrendView, string> = { volume: "Volume", sla: "SLA e ciclo", cancel: "Cancelamento" };
// Cauda da pergunta ao agente por métrica: "picos" e "cancelamento" caem nas regras certas do agente local.
const ASK_TAIL: Record<TrendView, string> = {
  volume: "onde estão os picos e o que fazer?",
  sla: "quando piora e o que fazer?",
  cancel: "onde estão os picos e o que fazer?",
};

function TrendChartInner() {
  const grain = useStore($view).grain;
  const view = useStore($view).trend;
  const [zoom, setZoom] = useState<{ start: string; end: string } | null>(null);
  const filters = useStore($filters);
  const chart = useRef<ECInstance | null>(null);
  const { data, error, isPending, refetch, isPlaceholderData, waking, down } = useRecorteQuery("/api/timeseries", { grain });
  const points = data ?? [];

  const summary = useMemo(() => {
    if (points.length === 0) return "";
    const stamp = (t: string) => (grain === "hour" ? fmt.dateTime(t) : fmt.date(t));
    const span = `${stamp(points[0].t)} a ${stamp(points.at(-1)!.t)}`;
    if (view === "volume") {
      let peak = points[0];
      for (const p of points) {
        if (p.orders > peak.orders) peak = p;
      }
      return `Tendência de volume (${span}, por ${GRAIN_LABEL[grain].toLowerCase()}). Pico: ${stamp(peak.t)} com ${fmt.int(peak.orders)} pedidos e ${fmt.brl(peak.gmv)} de GMV.`;
    }
    if (view === "sla") {
      const valid = points.filter((p) => p.sla_rate !== null);
      if (valid.length === 0) return `Tendência de SLA e ciclo (${span}).`;
      let worst = valid[0];
      let best = valid[0];
      for (const p of valid) {
        if ((p.sla_rate as number) < (worst.sla_rate as number)) worst = p;
        if ((p.sla_rate as number) > (best.sla_rate as number)) best = p;
      }
      return `Tendência de SLA (${span}). Pior ponto: ${stamp(worst.t)} com ${fmt.pct(worst.sla_rate)} no prazo (ciclo ${fmt.min(worst.cycle_p50)}). Melhor: ${stamp(best.t)} com ${fmt.pct(best.sla_rate)}.`;
    }
    const valid = points.filter((p) => p.cancel_rate !== null);
    if (valid.length === 0) return `Tendência de cancelamento (${span}).`;
    let peak = valid[0];
    let low = valid[0];
    for (const p of valid) {
      if ((p.cancel_rate as number) > (peak.cancel_rate as number)) peak = p;
      if ((p.cancel_rate as number) < (low.cancel_rate as number)) low = p;
    }
    return `Tendência de cancelamento (${span}). Maior taxa: ${stamp(peak.t)} com ${fmt.pct(peak.cancel_rate)}. Menor: ${stamp(low.t)} com ${fmt.pct(low.cancel_rate)}.`;
  }, [points, view, grain]);

  // O zoom pertence à faixa que está na tela. Recorte, granularidade, métrica ou
  // dados novos zeram o dataZoom do ECharts (notMerge), então o zoom guardado vira obsoleto.
  useEffect(() => {
    setZoom(null);
  }, [filters, grain, view, data]);

  const option = useCallback(
    (t: Tokens) => {
      const x = points.map((p) => p.t);
      const common = {
        grid: { left: 52, right: 52, top: 56, bottom: 64 },
        tooltip: { trigger: "axis" },
        legend: { top: 0, left: 0, itemWidth: 14, itemHeight: 8 },
        xAxis: { type: "category", data: x, axisLabel: { formatter: (v: string) => (grain === "hour" ? fmt.dateTime(v) : fmt.date(v)) } },
        dataZoom: [
          { type: "inside", throttle: 50 },
          {
            type: "slider",
            height: 18,
            bottom: 8,
            borderColor: t.rule,
            fillerColor: `${t.series}22`,
            handleStyle: { color: t.series, borderColor: t.series },
            moveHandleStyle: { color: t.series },
            dataBackground: { lineStyle: { color: t.muted }, areaStyle: { color: t.sunken } },
            textStyle: { color: t.muted },
            labelFormatter: (_: number, v: string) => fmt.date(v),
          },
        ],
      };
      if (view === "volume") {
        return {
          ...common,
          yAxis: [
            { type: "value", name: "Pedidos", nameTextStyle: { color: t.muted } },
            { type: "value", name: "GMV", nameTextStyle: { color: t.muted }, splitLine: { show: false }, axisLabel: { formatter: (v: number) => fmt.brlCompact(v) } },
          ],
          series: [
            { id: "pedidos", name: "Pedidos", type: "bar", data: points.map((p) => p.orders), itemStyle: { color: t.series }, large: true },
            {
              id: "gmv",
              name: "GMV",
              type: "line",
              yAxisIndex: 1,
              data: points.map((p) => p.gmv),
              showSymbol: false,
              lineStyle: { color: t.ink, width: 2.5 },
              itemStyle: { color: t.ink },
              tooltip: { valueFormatter: (v: number) => fmt.brl(v) },
            },
          ],
        };
      }
      if (view === "sla") {
        return {
          ...common,
          yAxis: [
            { type: "value", name: "No prazo", min: (v: { min: number }) => Math.max(0, Math.floor(v.min * 10) / 10), max: 1, axisLabel: { formatter: (v: number) => fmt.pct(v) } },
            { type: "value", name: "Ciclo (min)", splitLine: { show: false } },
          ],
          series: [
            {
              id: "no-prazo",
              name: "No prazo",
              type: "line",
              data: points.map((p) => p.sla_rate),
              showSymbol: false,
              lineStyle: { color: t.ink, width: 2.5 },
              itemStyle: { color: t.ink },
              tooltip: { valueFormatter: (v: number) => fmt.pct(v) },
            },
            {
              id: "ciclo-mediano",
              name: "Ciclo mediano",
              type: "line",
              yAxisIndex: 1,
              data: points.map((p) => p.cycle_p50),
              showSymbol: false,
              lineStyle: { color: t.muted, width: 1.5, type: "dashed" },
              itemStyle: { color: t.muted },
              tooltip: { valueFormatter: (v: number) => fmt.min(v) },
            },
          ],
        };
      }
      return {
        ...common,
        yAxis: [{ type: "value", axisLabel: { formatter: (v: number) => fmt.pct(v) } }],
        series: [
          {
            id: "cancelamento",
            name: "Cancelamento",
            type: "line",
            data: points.map((p) => p.cancel_rate),
            showSymbol: false,
            areaStyle: { color: `${t.ink}14` },
            lineStyle: { color: t.ink, width: 2.5 },
            itemStyle: { color: t.ink },
            tooltip: { valueFormatter: (v: number) => fmt.pct(v) },
          },
        ],
      };
    },
    [points, view, grain],
  );

  const onZoom = useCallback(
    (_: unknown, c: ECInstance) => {
      const opt = c.getOption() as { dataZoom?: { startValue?: number; endValue?: number }[] };
      const z = opt.dataZoom?.[0];
      if (!z || z.startValue === undefined || z.endValue === undefined || points.length === 0) return;
      const s = points[z.startValue]?.t.slice(0, 10);
      const e = points[z.endValue]?.t.slice(0, 10);
      const full = z.startValue === 0 && z.endValue === points.length - 1;
      setZoom(!full && s && e ? { start: s, end: e } : null);
    },
    [points],
  );

  const applyZoom = () => {
    if (!zoom) return;
    patchFilters({ start: zoom.start, end: zoom.end });
    setZoom(null);
  };

  const clearZoom = () => {
    chart.current?.dispatchAction({ type: "dataZoom", start: 0, end: 100 });
    setZoom(null);
  };

  return (
    <PanelContent
      hint={
        zoom
          ? `Zoom em ${fmt.date(zoom.start)} a ${fmt.date(zoom.end)}. Aplique para levar o período a todo o painel.`
          : "Arraste no gráfico ou na barra inferior para dar zoom; o zoom pode virar o período do recorte."
      }
      busy={isPlaceholderData}
      actions={
        <>
          {zoom && (
            <>
              <button type="button" className="btn-ghost py-1 text-aux" onClick={clearZoom}>
                <X className="size-3.5" aria-hidden /> Limpar zoom
              </button>
              <button type="button" className="btn-ink py-1 text-aux" onClick={applyZoom}>
                <CalendarCheck className="size-3.5" aria-hidden /> Usar como período
              </button>
            </>
          )}
          <Segmented
            label="Métrica"
            value={view}
            onChange={(value) => setView({ trend: value })}
            options={(Object.keys(VIEW_LABEL) as TrendView[]).map((value) => ({ value, label: VIEW_LABEL[value] }))}
          />
          <Segmented
            label="Granularidade"
            value={grain}
            onChange={(value) => setView({ grain: value })}
            options={(Object.keys(GRAIN_LABEL) as TrendGrain[]).map((value) => ({ value, label: GRAIN_LABEL[value] }))}
          />
          <AskAgentButton
            subject={`a tendência de ${VIEW_LABEL[view].toLowerCase()}`}
            question={`Explique a tendência de ${VIEW_LABEL[view].toLowerCase()} por ${GRAIN_LABEL[grain].toLowerCase()} neste recorte: ${ASK_TAIL[view]}`}
          />
        </>
      }
    >
      <AsyncBody
        waking={waking}
        pending={isPending}
        error={error}
        down={down}
        onRetry={() => refetch()}
        what="a tendência"
        height={CHART_H}
        empty={points.length === 0 ? <Empty /> : null}
      >
        <div className="content-reveal min-w-0">
          <EChart
            option={option}
            height={CHART_H}
            onEvents={{ datazoom: onZoom }}
            onReady={(c) => (chart.current = c)}
            ariaLabel={`Série ${VIEW_LABEL[view]} por ${GRAIN_LABEL[grain].toLowerCase()} no recorte`}
          />
          <ChartAccess summary={summary} items={[]} />
        </div>
      </AsyncBody>
    </PanelContent>
  );
}

export default island(TrendChartInner, panelFallback(CHART_H, { hint: true }));
