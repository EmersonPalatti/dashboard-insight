import { useCallback } from "react";
import { applyDrilldown } from "@/lib/filters";
import { fmt } from "@/lib/format";
import { island, useRecorteQuery } from "@/lib/query";
import { EChart, type Tokens } from "./charts/EChart";
import { Empty, ErrorState, Panel, Skeleton } from "./ui/Panel";

const STAGES = [
  { key: "production_p50", label: "Preparo na loja" },
  { key: "collected_p50", label: "Coleta" },
  { key: "expedition_p50", label: "Expedição" },
  { key: "transit_p50", label: "Trânsito" },
] as const;

function StagesChartInner() {
  const { data, error, isPending, refetch, isPlaceholderData } = useRecorteQuery("/api/breakdown", {
    by: "hub",
    sort: "orders",
    limit: 14,
    min_orders: 200,
  });
  const rows = [...(data?.rows ?? [])].filter((r) => r.cycle_p50 !== null).reverse();

  const option = useCallback(
    (t: Tokens) => {
      const colors = [t.chili, t.amber, t.muted, t.chiliDeep];
      return {
        grid: { left: 8, right: 24, top: 30, bottom: 8, containLabel: true },
        legend: { top: 0, left: 0, itemWidth: 12, itemHeight: 8 },
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow" },
          valueFormatter: (v: number) => fmt.min(v),
        },
        xAxis: { type: "value", axisLabel: { formatter: (v: number) => `${v} min` } },
        yAxis: { type: "category", data: rows.map((r) => r.label), axisLabel: { color: t.ink } },
        series: STAGES.map((s, i) => ({
          name: s.label,
          type: "bar",
          stack: "ciclo",
          barMaxWidth: 18,
          data: rows.map((r) => r[s.key]),
          itemStyle: { color: colors[i] },
          emphasis: { focus: "series" },
        })),
      };
    },
    [rows],
  );

  return (
    <Panel
      title="Onde o tempo vai, por hub"
      hint="Mediana de cada etapa, sem pedidos presos. Clique numa barra para filtrar o hub."
      busy={isPlaceholderData}
    >
      {isPending ? (
        <Skeleton height={340} />
      ) : error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : rows.length === 0 ? (
        <Empty>Nenhum hub com 200+ pedidos no recorte.</Empty>
      ) : (
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
      )}
    </Panel>
  );
}

export default island(StagesChartInner);
