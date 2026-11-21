import { useCallback, useMemo } from "react";
import { applyDrilldown } from "@/lib/filters";
import { EVIDENCE_DIM } from "@/lib/evidence";
import { fmt } from "@/lib/format";
import { island, useRecorteQuery } from "@/lib/query";
import { BarChart } from "echarts/charts";
import { LegendComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { ChartAccess } from "./charts/ChartAccess";
import { EChart, escapeHtml, type Tokens } from "./charts/EChart";
import { AskAgentButton } from "./ui/AskAgentButton";
import { EvidenceTag, useEvidence } from "./ui/EvidenceTag";
import { AsyncBody, Empty, panelFallback, PanelContent } from "./ui/Panel";

// Módulos deste gráfico: barras empilhadas e legenda. O resto fica em charts/EChart.tsx.
echarts.use([BarChart, LegendComponent]);

const TOP_HUBS = 14;
const ROW_H = 26;
const CHROME_H = 50;

/**
 * Altura reservada do gráfico (teto de 14 hubs): skeleton, fallback do SSR e área mínima
 * coincidem com a altura renderizada no recorte padrão, evitando salto de layout.
 */
const CHART_H = TOP_HUBS * ROW_H + CHROME_H;

// Apenas as três etapas mutuamente exclusivas do ciclo (coleta é subetapa da expedição).
const STAGES = [
  { key: "production_p50", label: "Preparo na loja" },
  { key: "expedition_p50", label: "Expedição" },
  { key: "transit_p50", label: "Trânsito" },
] as const;

function StagesChartInner() {
  const { data, error, isPending, refetch, isPlaceholderData, waking, down } = useRecorteQuery("/api/breakdown", {
    by: "hub",
    sort: "orders",
    limit: 60,
    min_orders: 200,
  });
  // comanda aberta que aponta para um hub: ele fica no topo, cheio, e os outros recuam
  const focus = useEvidence("stages");
  const markedKey = (focus?.evidence.hubs ?? []).map(String).join(",");
  const marked = useMemo(() => new Set(markedKey ? markedKey.split(",") : []), [markedKey]);

  const { rows, anyMarked } = useMemo(() => {
    const withCycle = (data?.rows ?? []).filter((r) => r.cycle_p50 !== null);
    // Os 14 hubs com mais pedidos; se a comanda marcar algum fora deles, ele entra sem ultrapassar o teto.
    const extra = withCycle.slice(TOP_HUBS).filter((r) => marked.has(String(r.key))).slice(0, TOP_HUBS);
    const top = withCycle.slice(0, Math.max(0, TOP_HUBS - extra.length));
    const pool = [...top, ...extra];
    const pinned = pool.filter((r) => marked.has(String(r.key)));
    const others = pool.filter((r) => !marked.has(String(r.key)));
    // No ECharts o índice 0 fica embaixo. Inverter os demais e depois os marcados põe o hub da comanda no topo.
    return {
      rows: [...others].reverse().concat([...pinned].reverse()),
      anyMarked: pinned.length > 0,
    };
  }, [data, marked]);

  const summary = useMemo(() => {
    if (rows.length === 0) return "";
    const slowest = rows.reduce(
      (best, row) => ((row.cycle_p50 ?? -Infinity) > (best.cycle_p50 ?? -Infinity) ? row : best),
      rows[0],
    );
    const fastest = rows.reduce(
      (best, row) => ((row.cycle_p50 ?? Infinity) < (best.cycle_p50 ?? Infinity) ? row : best),
      rows[0],
    );
    return slowest === fastest
      ? `${slowest.label}: ciclo mediano de ${fmt.min(slowest.cycle_p50)}.`
      : `Mais lento: ${slowest.label}, ciclo mediano de ${fmt.min(slowest.cycle_p50)}. Mais rápido: ${fastest.label}, ${fmt.min(fastest.cycle_p50)}.`;
  }, [rows]);

  const option = useCallback(
    (t: Tokens) => {
      const colors = [t.seriesDeep, t.series, t.seriesSoft];
      return {
        grid: { left: 8, right: 24, top: 30, bottom: 8, containLabel: true },
        legend: { top: 0, left: 0, itemWidth: 12, itemHeight: 8 },
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow" },
          formatter: (params: unknown) => {
            const items = (Array.isArray(params) ? params : [params]) as {
              dataIndex?: number;
              seriesName?: string;
              marker?: string;
              value?: unknown;
            }[];
            const idx = items[0]?.dataIndex;
            const row = typeof idx === "number" ? rows[idx] : undefined;
            if (!row) return "";
            const lines = [`<b>${escapeHtml(row.label)}</b>`];
            for (const item of items) {
              const val = typeof item.value === "number" ? item.value : null;
              lines.push(`${item.marker ?? ""}${escapeHtml(item.seriesName ?? "")}: <b>${escapeHtml(fmt.min(val))}</b>`);
            }
            lines.push(`Coleta (subetapa da expedição): <b>${escapeHtml(fmt.min(row.collected_p50))}</b>`);
            lines.push(`Ciclo mediano: <b>${escapeHtml(fmt.min(row.cycle_p50))}</b>`);
            return lines.join("<br/>");
          },
        },
        xAxis: { type: "value", splitNumber: 4, axisLabel: { hideOverlap: true, formatter: (v: number) => (v === 0 ? "0" : `${v} min`) } },
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
    [rows, anyMarked, marked],
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
            height={Math.max(220, rows.length * ROW_H + CHROME_H)}
            ariaLabel="Barras empilhadas com a mediana de cada etapa por hub"
            onEvents={{
              click: (p: unknown) => {
                const idx =
                  typeof p === "object" && p !== null && "dataIndex" in p
                    ? (p as { dataIndex?: unknown }).dataIndex
                    : undefined;
                const row = typeof idx === "number" ? rows[idx] : undefined;
                if (row && row.key != null) applyDrilldown({ hub: [Number(row.key)] });
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
