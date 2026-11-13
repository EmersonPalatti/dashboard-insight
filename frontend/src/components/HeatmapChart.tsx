import { useCallback, useEffect, useMemo, useState } from "react";
import { EVIDENCE_DIM } from "@/lib/evidence";
import { fmt, WEEKDAYS } from "@/lib/format";
import { island, useRecorteQuery } from "@/lib/query";
import { HeatmapChart } from "echarts/charts";
import { VisualMapComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { ChartAccess } from "./charts/ChartAccess";
import { EChart, type Tokens } from "./charts/EChart";
import { AskAgentButton } from "./ui/AskAgentButton";
import { EvidenceTag, useEvidence } from "./ui/EvidenceTag";
import { AsyncBody, Empty, panelFallback, PanelContent, Segmented } from "./ui/Panel";

// Módulos deste gráfico: mapa de calor e visualMap (escala de cor). O resto fica em charts/EChart.tsx.
echarts.use([HeatmapChart, VisualMapComponent]);

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
  const { data, error, isPending, refetch, isPlaceholderData, waking, down } = useRecorteQuery("/api/heatmap");
  // comanda aberta que aponta para horas: o mapa passa para a métrica dela, as horas ficam cheias e o resto recua
  const focus = useEvidence("heatmap");
  const focusMetric = focus?.evidence.metric;
  const focusId = focus?.alertId;
  useEffect(() => {
    if (focusMetric) setMetric(focusMetric);
  }, [focusId, focusMetric]);
  const peak = useMemo(() => new Set(focus?.evidence.hours ?? []), [focus]);
  const cells = data ?? [];
  // Células que entram no mapa para a métrica atual: taxas só com MIN_ORDERS pedidos e valor presente.
  const usable = useMemo(
    () => cells.filter((c) => (metric === "orders" || c.orders >= MIN_ORDERS) && c[metric] !== null),
    [cells, metric],
  );
  const summary = useMemo(() => {
    if (usable.length === 0) return "";
    const m = METRICS[metric];
    let hi = usable[0];
    let lo = usable[0];
    for (const c of usable) {
      if ((c[metric] as number) > (hi[metric] as number)) hi = c;
      if ((c[metric] as number) < (lo[metric] as number)) lo = c;
    }
    if (hi === lo) {
      return `${m.label}: ${WEEKDAYS[hi.weekday]} às ${HOURS[hi.hour]} (${m.format(hi[metric] as number)}, ${fmt.int(hi.orders)} pedidos).`;
    }
    return `Maior ${m.label.toLowerCase()}: ${WEEKDAYS[hi.weekday]} às ${HOURS[hi.hour]} (${m.format(hi[metric] as number)}, ${fmt.int(hi.orders)} pedidos). Menor: ${WEEKDAYS[lo.weekday]} às ${HOURS[lo.hour]} (${m.format(lo[metric] as number)}).`;
  }, [usable, metric]);

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
        xAxis: {
          type: "category",
          data: HOURS,
          splitArea: { show: false },
          axisLabel: peak.size
            ? {
                interval: 0,
                // com horas marcadas, todas aparecem: as da comanda em tinta, as outras só nas pares
                formatter: (v: string, i: number) => (peak.has(i) ? `{hl|${v}}` : i % 2 === 0 ? v : ""),
                rich: { hl: { color: t.ink, fontWeight: "bold" } },
              }
            : { interval: 1 },
        },
        yAxis: { type: "category", data: WEEKDAYS, inverse: true, splitLine: { show: false }, axisLine: { show: false } },
        visualMap: {
          // a cor vem da métrica (coluna 2); sem isto o ECharts usa a última coluna, que é a contagem de pedidos
          dimension: 2,
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
            data: peak.size
              ? values.map((v) => ({
                  value: v,
                  itemStyle: {
                    opacity: peak.has(v[0]) ? 1 : EVIDENCE_DIM,
                    borderWidth: peak.has(v[0]) ? 2 : 1,
                    borderColor: peak.has(v[0]) ? t.ink : t.surface,
                  },
                }))
              : values,
            itemStyle: { borderColor: t.surface, borderWidth: 1 },
            emphasis: { itemStyle: { borderColor: t.ink, borderWidth: 1 } },
          },
        ],
      };
    },
    [usable, metric, peak],
  );

  return (
    <PanelContent
      note={focus && <EvidenceTag focus={focus} />}
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
      <AsyncBody
        waking={waking}
        pending={isPending}
        error={error}
        down={down}
        onRetry={() => refetch()}
        what="o mapa dia × hora"
        height={CHART_H}
        empty={
          usable.length === 0 ? (
            <Empty>
              <span className="block">
                <span className="block font-semibold text-balance text-ink">
                  {cells.length === 0
                    ? "Sem pedidos neste recorte para montar o mapa de calor."
                    : `Nenhuma faixa de dia e hora chega a ${MIN_ORDERS} pedidos neste recorte.`}
                </span>
                <span className="mt-1 block text-pretty text-aux">
                  {cells.length === 0
                    ? "Afrouxe o período ou tire um filtro de hub, loja ou cidade para ver as faixas."
                    : "Troque a métrica para Pedidos ou amplie o período para as taxas aparecerem."}
                </span>
              </span>
            </Empty>
          ) : null
        }
      >
        <div className="content-reveal min-w-0">
          <EChart option={option} height={CHART_H} ariaLabel={`Mapa de calor de ${METRICS[metric].label} por dia e hora`} />
          <ChartAccess summary={summary} items={[]} />
        </div>
      </AsyncBody>
    </PanelContent>
  );
}

export default island(HeatmapChartInner, panelFallback(CHART_H, { hint: true }));
