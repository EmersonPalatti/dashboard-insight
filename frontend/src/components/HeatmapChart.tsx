import { useCallback, useMemo, useState } from "react";
import { fmt, WEEKDAYS } from "@/lib/format";
import { island, useRecorteQuery } from "@/lib/query";
import { EChart, type Tokens } from "./charts/EChart";
import { AskAgentButton } from "./ui/AskAgentButton";
import { Empty, ErrorState, Panel, Segmented, Skeleton } from "./ui/Panel";

type Metric = "orders" | "sla_rate" | "cancel_rate" | "cycle_p50";

const METRICS: Record<Metric, { label: string; format: (v: number) => string; worseIsHigh: boolean }> = {
  orders: { label: "Pedidos", format: fmt.int, worseIsHigh: true },
  sla_rate: { label: "No prazo", format: fmt.pct, worseIsHigh: false },
  cancel_rate: { label: "Cancelamento", format: fmt.pct, worseIsHigh: true },
  cycle_p50: { label: "Ciclo", format: fmt.min, worseIsHigh: true },
};

// Pergunta por métrica do mapa: cada uma cai numa regra do agente local (ver backend/app/agent/local.py).
const ASK_BY_METRIC: Record<Metric, string> = {
  orders: "Onde estão os picos de pedidos por dia e hora neste recorte e o que fazer?",
  sla_rate: "Em quais dias e horas o SLA piora neste recorte e o que fazer?",
  cancel_rate: "Em quais dias e horas o cancelamento sobe neste recorte e o que fazer?",
  cycle_p50: "Em quais dias e faixas o ciclo fica mais longo neste recorte e o que fazer?",
};

const HOURS = Array.from({ length: 24 }, (_, h) => `${String(h).padStart(2, "0")}h`);
const MIN_ORDERS = 20; // células com pouco pedido viram ruído em taxas
const CHART_H = 300;

function HeatmapChartInner() {
  const [metric, setMetric] = useState<Metric>("orders");
  const { data, error, isPending, refetch, isPlaceholderData } = useRecorteQuery("/api/heatmap");
  const cells = data ?? [];
  // Células que entram no mapa para a métrica atual: taxas só com MIN_ORDERS pedidos e valor presente.
  const usable = useMemo(
    () => cells.filter((c) => (metric === "orders" || c.orders >= MIN_ORDERS) && c[metric] !== null),
    [cells, metric],
  );

  const option = useCallback(
    (t: Tokens) => {
      const m = METRICS[metric];
      const values = usable.map((c) => [c.hour, c.weekday, c[metric], c.orders] as const);
      const nums = values.map((v) => v[2] as number);
      const lo = Math.min(...nums);
      const hi = Math.max(...nums);
      const scale = [t.sunken, t.seriesSoft, t.series, t.seriesDeep];
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
            itemStyle: { borderColor: t.surface, borderWidth: 1 },
            emphasis: { itemStyle: { borderColor: t.ink, borderWidth: 1 } },
          },
        ],
      };
    },
    [usable, metric],
  );

  return (
    <Panel
      title="Dia × hora"
      hint={metric === "orders" ? "Volume por faixa (horário de Brasília)." : `Taxas só em faixas com ${MIN_ORDERS}+ pedidos.`}
      busy={isPlaceholderData}
      actions={
        <>
          <Segmented
            label="Métrica do mapa de calor"
            value={metric}
            onChange={setMetric}
            options={(Object.keys(METRICS) as Metric[]).map((k) => ({ value: k, label: METRICS[k].label }))}
          />
          <AskAgentButton subject={`o mapa de ${METRICS[metric].label.toLowerCase()} por dia e hora`} question={ASK_BY_METRIC[metric]} />
        </>
      }
    >
      {isPending ? (
        <Skeleton height={CHART_H} />
      ) : error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : (
        <div className="content-reveal min-w-0">
          {usable.length === 0 ? (
            // Mesma altura do gráfico: trocar de estado não empurra o layout.
            <div className="flex items-center justify-center" style={{ height: CHART_H }}>
              <Empty>
                {/* Empty é flex em linha: um único filho bloco mantém as duas linhas empilhadas. */}
                <span className="block">
                  <span className="block font-semibold text-balance text-ink">
                    {cells.length === 0
                      ? "Sem pedidos neste recorte para montar o mapa de calor."
                      : `Nenhuma faixa de dia e hora chega a ${MIN_ORDERS} pedidos neste recorte.`}
                  </span>
                  <span className="mt-1 block text-pretty text-[0.85rem]">
                    {cells.length === 0
                      ? "Afrouxe o período ou tire um filtro de hub, loja ou cidade para ver as faixas."
                      : "Troque a métrica para Pedidos ou amplie o período para as taxas aparecerem."}
                  </span>
                </span>
              </Empty>
            </div>
          ) : (
            <EChart option={option} height={CHART_H} ariaLabel={`Mapa de calor de ${METRICS[metric].label} por dia e hora`} />
          )}
        </div>
      )}
    </Panel>
  );
}

export default island(HeatmapChartInner);
