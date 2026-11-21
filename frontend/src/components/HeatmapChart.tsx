import { useCallback, useEffect, useMemo, useState } from "react";
import type { GetResponse } from "@/lib/api/client";
import { EVIDENCE_DIM } from "@/lib/evidence";
import { fmt, WEEKDAYS } from "@/lib/format";
import { island, useMeta, useRecorteQuery } from "@/lib/query";
import { HeatmapChart } from "echarts/charts";
import { VisualMapComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { ChartAccess } from "./charts/ChartAccess";
import { EChart, escapeHtml, type Tokens } from "./charts/EChart";
import { AskAgentButton } from "./ui/AskAgentButton";
import { EvidenceTag, useEvidence } from "./ui/EvidenceTag";
import { AsyncBody, Empty, panelFallback, PanelContent, Segmented } from "./ui/Panel";

// Módulos deste gráfico: mapa de calor e visualMap (escala de cor). O resto fica em charts/EChart.tsx.
echarts.use([HeatmapChart, VisualMapComponent]);

export type Metric = "orders" | "sla_rate" | "cancel_rate" | "cycle_p50";

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
const CHART_H = 300;
export type Cell = GetResponse<"/api/heatmap">[number];
// Lista vazia estável: sem dados, `cells` não muda de referência a cada render.
const EMPTY: Cell[] = [];

function isThinCell(cell: Cell, metric: Metric): boolean {
  if (metric === "orders") return false;
  return metric === "cancel_rate" ? cell.volume_low_sample : cell.low_sample;
}

/**
 * Opção do ECharts para o mapa. Pura (exportada para teste): células firmes puxam a escala;
 * as de amostra pequena entram na mesma série, cinzas e com a nota no tooltip.
 */
export function heatmapOption(
  t: Tokens,
  { firm, thin, metric, peak }: { firm: Cell[]; thin: Cell[]; metric: Metric; peak: ReadonlySet<number> },
) {
  const m = METRICS[metric];
  const toTuple = (c: Cell, thinFlag: 0 | 1) =>
    [c.hour, c.weekday, c[metric] as number, c.orders, c.measured, thinFlag] as const;
  const values = firm.map((c) => toTuple(c, 0));
  const thinValues = thin.map((c) => toTuple(c, 1));
  const nums = values.map((v) => v[2]);
  const lo = nums.length > 0 ? Math.min(...nums) : 0;
  const hi = nums.length > 0 ? Math.max(...nums) : 1;
  const scale = [t.sunken, t.seriesSoft, t.series, t.seriesDeep];
  return {
    grid: { left: 44, right: 12, top: 8, bottom: 56 },
    tooltip: {
      formatter: (p: { value?: unknown }) => {
        const v = Array.isArray(p.value) ? (p.value as [number, number, number, number, number, number]) : null;
        if (!v) return "";
        const [hour, weekday, val, orders, measured, isThin] = v;
        const baseText =
          metric === "sla_rate" || metric === "cycle_p50"
            ? `${fmt.int(orders)} pedidos (${fmt.int(measured)} entregas medidas)`
            : `${fmt.int(orders)} pedidos`;
        const thinNote =
          isThin === 1 ? `<br/><span style="color:${t.muted}">Amostra pequena (fora da escala)</span>` : "";
        return `${escapeHtml(WEEKDAYS[weekday])} ${escapeHtml(HOURS[hour])}<br/>${escapeHtml(m.label)}: <b>${escapeHtml(m.format(val))}</b><br/>${escapeHtml(baseText)}${thinNote}`;
      },
    },
    xAxis: {
      type: "category",
      data: HOURS,
      splitArea: { show: false },
      axisLabel: peak.size
        ? {
            interval: 0,
            hideOverlap: true,
            // com horas marcadas, todas aparecem: as da comanda em tinta, as outras só nas pares
            formatter: (v: string, i: number) => (peak.has(i) ? `{hl|${v}}` : i % 2 === 0 ? v : ""),
            rich: { hl: { color: t.ink, fontWeight: "bold" } },
          }
        : { interval: 1, hideOverlap: true },
    },
    yAxis: { type: "category", data: WEEKDAYS, inverse: true, splitLine: { show: false }, axisLine: { show: false } },
    visualMap: {
      // A cor vem da métrica (coluna 2) e a escala só das células firmes (lo/hi). As cinzas ficam na
      // mesma série com cor própria no item: o itemStyle do item vence o visualMap no heatmap.
      // Uma segunda série heatmap sem visualMap quebra o ECharts ("Heatmap must use with visualMap").
      seriesIndex: 0,
      dimension: 2,
      min: lo,
      max: hi === lo ? lo + 1 : hi,
      calculable: false,
      orient: "horizontal",
      left: "center",
      bottom: 4,
      itemHeight: 110,
      itemWidth: 10,
      text:
        nums.length > 0
          ? m.worseIsHigh
            ? [`alto (${m.format(hi)})`, `baixo (${m.format(lo)})`]
            : [`melhor (${m.format(hi)})`, `pior (${m.format(lo)})`]
          : m.worseIsHigh
            ? ["alto", "baixo"]
            : ["melhor", "pior"],
      textStyle: { color: t.muted },
      formatter: (v: number) => m.format(v),
      inRange: { color: m.worseIsHigh ? scale : [...scale].reverse() },
    },
    series: [
      {
        id: "cells",
        type: "heatmap",
        data: [
          ...values.map((v) =>
            peak.size
              ? {
                  value: v,
                  itemStyle: {
                    opacity: peak.has(v[0]) ? 1 : EVIDENCE_DIM,
                    borderWidth: peak.has(v[0]) ? 2 : 1,
                    borderColor: peak.has(v[0]) ? t.ink : t.surface,
                  },
                }
              : v,
          ),
          ...thinValues.map((v) => ({
            value: v,
            itemStyle: peak.size
              ? {
                  color: t.rule,
                  opacity: peak.has(v[0]) ? 0.85 : EVIDENCE_DIM * 0.7,
                  borderWidth: peak.has(v[0]) ? 2 : 1,
                  borderColor: peak.has(v[0]) ? t.ink : t.surface,
                }
              : { color: t.rule, opacity: 0.6 },
          })),
        ],
        itemStyle: { borderColor: t.surface, borderWidth: 1 },
        emphasis: { itemStyle: { borderColor: t.ink, borderWidth: 1 } },
      },
    ],
  };
}

function HeatmapChartInner() {
  const [metric, setMetric] = useState<Metric>("orders");
  const { data, error, isPending, refetch, isPlaceholderData, waking, down } = useRecorteQuery("/api/heatmap");
  const { data: meta } = useMeta();
  const minSample = meta?.heatmap_min_sample ?? 20;
  // comanda aberta que aponta para horas: o mapa passa para a métrica dela, as horas ficam cheias e o resto recua
  const focus = useEvidence("heatmap");
  const focusMetric = focus?.evidence.metric;
  const focusId = focus?.alertId;
  useEffect(() => {
    if (focusMetric) setMetric(focusMetric);
  }, [focusId, focusMetric]);
  const peak = useMemo(() => new Set(focus?.evidence.hours ?? []), [focus]);
  const cells = data ?? EMPTY;
  // O backend marca quais células ficam fora da escala por amostra pequena; só as firmes puxam cor e extremos.
  const { firm, thin } = useMemo(() => {
    const firmRows: Cell[] = [];
    const thinRows: Cell[] = [];
    for (const c of cells) {
      if (c[metric] === null) continue;
      if (isThinCell(c, metric)) thinRows.push(c);
      else firmRows.push(c);
    }
    return { firm: firmRows, thin: thinRows };
  }, [cells, metric]);
  const summary = useMemo(() => {
    if (firm.length === 0) return "";
    const m = METRICS[metric];
    let hi = firm[0];
    let lo = firm[0];
    for (const c of firm) {
      if ((c[metric] as number) > (hi[metric] as number)) hi = c;
      if ((c[metric] as number) < (lo[metric] as number)) lo = c;
    }
    if (hi === lo) {
      return `${m.label}: ${WEEKDAYS[hi.weekday]} às ${HOURS[hi.hour]} (${m.format(hi[metric] as number)}, ${fmt.int(hi.orders)} pedidos).`;
    }
    return `Maior ${m.label.toLowerCase()}: ${WEEKDAYS[hi.weekday]} às ${HOURS[hi.hour]} (${m.format(hi[metric] as number)}, ${fmt.int(hi.orders)} pedidos). Menor: ${WEEKDAYS[lo.weekday]} às ${HOURS[lo.hour]} (${m.format(lo[metric] as number)}).`;
  }, [firm, metric]);

  const option = useCallback((t: Tokens) => heatmapOption(t, { firm, thin, metric, peak }), [firm, thin, metric, peak]);

  const hint =
    metric === "orders"
      ? "Volume por faixa (horário de Brasília)."
      : metric === "cancel_rate"
        ? `Escala só com ${minSample}+ pedidos; faixas cinzas têm amostra pequena.`
        : `Escala só com ${minSample}+ entregas medidas; faixas cinzas têm amostra pequena.`;

  return (
    <PanelContent
      note={focus && <EvidenceTag focus={focus} />}
      hint={hint}
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
          firm.length === 0 ? (
            <Empty>
              <span className="block">
                <span className="block font-semibold text-balance text-ink">
                  {cells.length === 0
                    ? "Sem pedidos neste recorte para montar o mapa de calor."
                    : metric === "cancel_rate"
                      ? `Nenhuma faixa de dia e hora chega a ${minSample} pedidos neste recorte.`
                      : `Nenhuma faixa de dia e hora chega a ${minSample} entregas medidas neste recorte.`}
                </span>
                <span className="mt-1 block text-pretty text-aux">
                  {cells.length === 0
                    ? "Afrouxe o período ou tire um filtro de hub, loja ou cidade para ver as faixas."
                    : "Troque a métrica para Pedidos ou amplie o período para as faixas firmes aparecerem."}
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
