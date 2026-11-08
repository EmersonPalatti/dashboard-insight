import { useCallback, useState } from "react";
import { fmt, WEEKDAYS } from "@/lib/format";
import { island, useRecorteQuery } from "@/lib/query";
import { EChart, type Tokens } from "./charts/EChart";
import { Empty, ErrorState, Panel, Segmented, Skeleton } from "./ui/Panel";

type Metric = "orders" | "sla_rate" | "cancel_rate" | "cycle_p50";

const METRICS: Record<Metric, { label: string; format: (v: number) => string; worseIsHigh: boolean }> = {
  orders: { label: "Pedidos", format: fmt.int, worseIsHigh: true },
  sla_rate: { label: "No prazo", format: fmt.pct, worseIsHigh: false },
  cancel_rate: { label: "Cancelamento", format: fmt.pct, worseIsHigh: true },
  cycle_p50: { label: "Ciclo", format: fmt.min, worseIsHigh: true },
};

const HOURS = Array.from({ length: 24 }, (_, h) => `${String(h).padStart(2, "0")}h`);
const MIN_ORDERS = 20; // células com pouco pedido viram ruído em taxas

function HeatmapChartInner() {
  const [metric, setMetric] = useState<Metric>("orders");
  const { data, error, isPending, refetch, isPlaceholderData } = useRecorteQuery("/api/heatmap");
  const cells = data ?? [];

  const option = useCallback(
    (t: Tokens) => {
      const m = METRICS[metric];
      const values = cells
        .filter((c) => metric === "orders" || c.orders >= MIN_ORDERS)
        .map((c) => [c.hour, c.weekday, c[metric], c.orders] as const)
        .filter((v) => v[2] !== null);
      const nums = values.map((v) => v[2] as number);
      const lo = Math.min(...nums);
      const hi = Math.max(...nums);
      const scale = [t.paper, t.chiliSoft, t.chili, t.chiliDeep];
      return {
        grid: { left: 44, right: 12, top: 8, bottom: 56 },
        tooltip: {
          formatter: (p: { value: [number, number, number, number] }) =>
            `${WEEKDAYS[p.value[1]]} ${HOURS[p.value[0]]}<br/>${m.label}: <b>${m.format(p.value[2])}</b><br/>${fmt.int(p.value[3])} pedidos`,
        },
        xAxis: { type: "category", data: HOURS, splitArea: { show: false }, axisLabel: { interval: 1 } },
        yAxis: { type: "category", data: WEEKDAYS, inverse: true, splitLine: { show: false }, axisLine: { show: false } },
        visualMap: {
          min: lo,
          max: hi === lo ? lo + 1 : hi,
          calculable: false,
          orient: "horizontal",
          left: "center",
          bottom: 4,
          itemHeight: 140,
          itemWidth: 10,
          text: m.worseIsHigh ? ["alto", "baixo"] : ["melhor", "pior"],
          textStyle: { color: t.muted },
          formatter: (v: number) => m.format(v),
          inRange: { color: m.worseIsHigh ? scale : [...scale].reverse() },
        },
        series: [
          {
            type: "heatmap",
            data: values,
            itemStyle: { borderColor: t.paper, borderWidth: 1 },
            emphasis: { itemStyle: { borderColor: t.ink, borderWidth: 1 } },
          },
        ],
      };
    },
    [cells, metric],
  );

  return (
    <Panel
      title="Dia × hora"
      hint={metric === "orders" ? "Volume por faixa (horário de Brasília)." : `Taxas só em faixas com ${MIN_ORDERS}+ pedidos.`}
      busy={isPlaceholderData}
      actions={
        <Segmented
          label="Métrica do mapa de calor"
          value={metric}
          onChange={setMetric}
          options={(Object.keys(METRICS) as Metric[]).map((k) => ({ value: k, label: METRICS[k].label }))}
        />
      }
    >
      {isPending ? (
        <Skeleton height={300} />
      ) : error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : cells.length === 0 ? (
        <Empty />
      ) : (
        <EChart option={option} height={300} ariaLabel={`Mapa de calor de ${METRICS[metric].label} por dia e hora`} />
      )}
    </Panel>
  );
}

export default island(HeatmapChartInner);
