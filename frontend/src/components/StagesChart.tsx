import { useCallback } from "react";
import { applyDrilldown } from "@/lib/filters";
import { EVIDENCE_DIM } from "@/lib/evidence";
import { fmt } from "@/lib/format";
import { island, useRecorteQuery } from "@/lib/query";
import { BarChart } from "echarts/charts";
import { LegendComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { ChartAccess } from "./charts/ChartAccess";
import { EChart, type Tokens } from "./charts/EChart";
import { AskAgentButton } from "./ui/AskAgentButton";
import { EvidenceTag, useEvidence } from "./ui/EvidenceTag";
import { AsyncBody, Empty, panelFallback, PanelContent } from "./ui/Panel";

// Módulos deste gráfico: barras empilhadas e legenda. O resto fica em charts/EChart.tsx.
echarts.use([BarChart, LegendComponent]);

/**
 * Altura reservada do gráfico: skeleton, fallback do SSR e área mínima do resultado.
 * O gráfico em si pode ser mais baixo (poucos hubs); a área reservada impede o layout de encolher.
 */
const CHART_H = 340;

const STAGES = [
  { key: "production_p50", label: "Preparo na loja" },
  { key: "collected_p50", label: "Coleta" },
  { key: "expedition_p50", label: "Expedição" },
  { key: "transit_p50", label: "Trânsito" },
] as const;

const TOP_HUBS = 14;

type StageRow = {
  key: string | number | null;
  label: string;
  production_p50: number | null;
  collected_p50: number | null;
  expedition_p50: number | null;
  transit_p50: number | null;
};

/** Soma das medianas das quatro etapas. Serve para dizer qual hub é o mais lento. */
function stageTotal(row: StageRow) {
  return STAGES.reduce((sum, stage) => sum + (row[stage.key] ?? 0), 0);
}

function StagesChartInner() {
  const { data, error, isPending, refetch, isPlaceholderData, waking, down } = useRecorteQuery("/api/breakdown", {
    by: "hub",
    sort: "orders",
    limit: 60,
    min_orders: 200,
  });
  // comanda aberta que aponta para um hub: ele fica no topo, cheio, e os outros recuam
  const focus = useEvidence("stages");
  const marked = new Set((focus?.evidence.hubs ?? []).map(String));
  // Os 14 hubs com mais pedidos; o hub da comanda entra se estiver fora deles.
  const withCycle = (data?.rows ?? []).filter((r) => r.cycle_p50 !== null);
  const top = withCycle.slice(0, TOP_HUBS);
  const extra = withCycle.slice(TOP_HUBS).filter((r) => marked.has(String(r.key)));
  const pool = [...top, ...extra];
  const pinned = pool.filter((r) => marked.has(String(r.key)));
  const others = pool.filter((r) => !marked.has(String(r.key)));
  // No ECharts o índice 0 fica embaixo. Inverter os demais e depois os marcados põe o hub da comanda no topo.
  const rows = [...others].reverse().concat([...pinned].reverse());
  const anyMarked = pinned.length > 0;
  const markedKey = [...marked].join(",");
  const slowest = rows.reduce((best, row) => (stageTotal(row) > stageTotal(best) ? row : best), rows[0]);
  const fastest = rows.reduce((best, row) => (stageTotal(row) < stageTotal(best) ? row : best), rows[0]);
  const summary =
    rows.length === 0
      ? ""
      : slowest === fastest
        ? `${slowest.label}: ${fmt.min(stageTotal(slowest))} somando as medianas das etapas.`
        : `Mais lento: ${slowest.label}, ${fmt.min(stageTotal(slowest))}. Mais rápido: ${fastest.label}, ${fmt.min(stageTotal(fastest))}. Soma das medianas das etapas.`;

  const option = useCallback(
    (t: Tokens) => {
      const colors = [t.seriesDeep, t.series, t.seriesSoft, t.muted];
      return {
        grid: { left: 8, right: 24, top: 30, bottom: 8, containLabel: true },
        legend: { top: 0, left: 0, itemWidth: 12, itemHeight: 8 },
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow" },
          valueFormatter: (v: number) => fmt.min(v),
        },
        xAxis: { type: "value", axisLabel: { formatter: (v: number) => `${v} min` } },
        yAxis: {
          type: "category",
          data: rows.map((r) => r.label),
          axisLabel: {
            color: anyMarked ? t.muted : t.ink,
            formatter: (v: string, i: number) =>
              anyMarked && marked.has(String(rows[i]?.key ?? "")) ? `{dot|●} {hl|${v}}` : v,
            rich: {
              dot: { color: t.ink, fontSize: 10, padding: [0, 4, 0, 0] },
              hl: { color: t.ink, fontWeight: "bold" },
            },
          },
        },
        series: STAGES.map((s, i) => ({
          id: s.key,
          name: s.label,
          type: "bar",
          stack: "ciclo",
          barMaxWidth: 18,
          data: rows.map((r) => ({
            value: r[s.key],
            itemStyle: { opacity: anyMarked && !marked.has(String(r.key)) ? EVIDENCE_DIM : 1 },
          })),
          itemStyle: { color: colors[i] },
          emphasis: { focus: "series" },
        })),
      };
    },
    [rows, anyMarked, markedKey], // eslint-disable-line react-hooks/exhaustive-deps
  );

  return (
    <PanelContent
      note={
        focus && (
          <EvidenceTag
            focus={focus}
            note={anyMarked ? undefined : `${focus.title} · hub com menos de 200 pedidos, fora deste gráfico`}
          />
        )
      }
      busy={isPlaceholderData}
      actions={
        <AskAgentButton
          subject="o tempo por etapa e hub"
          question="Onde está o gargalo do ciclo por hub neste recorte e o que fazer?"
        />
      }
    >
      <AsyncBody
        waking={waking}
        pending={isPending}
        error={error}
        down={down}
        onRetry={() => refetch()}
        what="as etapas por hub"
        height={CHART_H}
        empty={rows.length === 0 ? <Empty>Nenhum hub com 200+ pedidos no recorte.</Empty> : null}
      >
        <div className="content-reveal min-w-0" style={{ minHeight: CHART_H }}>
          <EChart
            option={option}
            height={Math.max(220, rows.length * 26 + 50)}
            ariaLabel="Barras empilhadas com a mediana de cada etapa por hub"
            onEvents={{
              click: (p: { dataIndex: number }) => {
                const row = rows[p.dataIndex];
                if (row) applyDrilldown({ hub: [Number(row.key)] });
              },
            }}
          />
          <ChartAccess
            summary={summary}
            items={[...rows].reverse().flatMap((row) =>
              row.key == null
                ? []
                : [
                    {
                      key: String(row.key),
                      label: `Filtrar hub ${row.label}`,
                      onSelect: () => applyDrilldown({ hub: [Number(row.key)] }),
                    },
                  ],
            )}
          />
        </div>
      </AsyncBody>
    </PanelContent>
  );
}

export default island(StagesChartInner, panelFallback(CHART_H));
