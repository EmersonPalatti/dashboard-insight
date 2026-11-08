import { useStore } from "@nanostores/react";
import { CalendarCheck } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { $filters, patchFilters } from "@/lib/filters";
import { fmt } from "@/lib/format";
import { island, useRecorteQuery } from "@/lib/query";
import { EChart, type ECInstance, type Tokens } from "./charts/EChart";
import { Empty, ErrorState, Panel, Segmented, Skeleton } from "./ui/Panel";

type Grain = "hour" | "day" | "week";
type View = "volume" | "sla" | "cancel";

const GRAIN_LABEL: Record<Grain, string> = { hour: "Hora", day: "Dia", week: "Semana" };
const VIEW_LABEL: Record<View, string> = { volume: "Volume", sla: "SLA e ciclo", cancel: "Cancelamento" };

function TrendChartInner() {
  const [grain, setGrain] = useState<Grain>("day");
  const [view, setView] = useState<View>("volume");
  const [zoom, setZoom] = useState<{ start: string; end: string } | null>(null);
  const filters = useStore($filters);
  const chart = useRef<ECInstance | null>(null);
  const { data, error, isPending, refetch, isPlaceholderData } = useRecorteQuery("/api/timeseries", { grain });
  const points = data ?? [];

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

  return (
    <Panel
      title="Tendência"
      hint={
        zoom
          ? `Zoom em ${fmt.date(zoom.start)} a ${fmt.date(zoom.end)}. Aplique para levar o período a todo o painel.`
          : "Arraste no gráfico ou na barra inferior para dar zoom; o zoom pode virar o período do recorte."
      }
      busy={isPlaceholderData}
      actions={
        <>
          {zoom && (
            <button type="button" className="btn-ink py-1 text-[0.85rem]" onClick={applyZoom}>
              <CalendarCheck className="size-3.5" aria-hidden /> Usar como período
            </button>
          )}
          <Segmented
            label="Métrica"
            value={view}
            onChange={setView}
            options={(Object.keys(VIEW_LABEL) as View[]).map((value) => ({ value, label: VIEW_LABEL[value] }))}
          />
          <Segmented
            label="Granularidade"
            value={grain}
            onChange={setGrain}
            options={(Object.keys(GRAIN_LABEL) as Grain[]).map((value) => ({ value, label: GRAIN_LABEL[value] }))}
          />
        </>
      }
    >
      {isPending ? (
        <Skeleton height={340} />
      ) : error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : points.length === 0 ? (
        <Empty />
      ) : (
        <div className="content-reveal min-w-0">
          <EChart
            option={option}
            height={340}
            onEvents={{ datazoom: onZoom }}
            onReady={(c) => (chart.current = c)}
            ariaLabel={`Série ${VIEW_LABEL[view]} por ${GRAIN_LABEL[grain].toLowerCase()} no recorte`}
          />
        </div>
      )}
    </Panel>
  );
}

export default island(TrendChartInner, 430);
