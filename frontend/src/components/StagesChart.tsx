import { useCallback } from "react";
import { applyDrilldown } from "@/lib/filters";
import { fmt } from "@/lib/format";
import { island, useRecorteQuery } from "@/lib/query";
import { BarChart } from "echarts/charts";
import { LegendComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { EChart, type Tokens } from "./charts/EChart";
import { AskAgentButton } from "./ui/AskAgentButton";
import { EvidenceTag, useEvidence } from "./ui/EvidenceTag";
import { Empty, ErrorState, panelFallback, PanelContent, Skeleton } from "./ui/Panel";

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

function StagesChartInner() {
  const { data, error, isPending, refetch, isPlaceholderData } = useRecorteQuery("/api/breakdown", {
    by: "hub",
    sort: "orders",
    limit: 60,
    min_orders: 200,
  });
  // comanda aberta que aponta para um hub: ele fica cheio e os outros recuam
  const focus = useEvidence("stages");
  const marked = new Set((focus?.evidence.hubs ?? []).map(String));
  // Os 14 hubs com mais pedidos; o hub da comanda entra no fim se estiver fora deles.
  const withCycle = (data?.rows ?? []).filter((r) => r.cycle_p50 !== null);
  const top = withCycle.slice(0, TOP_HUBS);
  const extra = withCycle.slice(TOP_HUBS).filter((r) => marked.has(String(r.key)));
  const rows = [...top, ...extra].reverse();
  const anyMarked = rows.some((r) => marked.has(String(r.key)));
  const markedKey = [...marked].join(",");

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
            formatter: (v: string, i: number) => (anyMarked && marked.has(String(rows[i]?.key ?? "")) ? `{hl|${v}}` : v),
            rich: { hl: { color: t.ink, fontWeight: "bold" } },
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
            itemStyle: { opacity: anyMarked && !marked.has(String(r.key)) ? 0.28 : 1 },
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
      {isPending ? (
        <Skeleton height={CHART_H} />
      ) : error ? (
        <div className="flex items-center justify-center" style={{ minHeight: CHART_H }}>
          <ErrorState error={error} onRetry={() => refetch()} />
        </div>
      ) : rows.length === 0 ? (
        <div className="flex items-center justify-center" style={{ minHeight: CHART_H }}>
          <Empty>Nenhum hub com 200+ pedidos no recorte.</Empty>
        </div>
      ) : (
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
        </div>
      )}
    </PanelContent>
  );
}

export default island(StagesChartInner, panelFallback(CHART_H));
